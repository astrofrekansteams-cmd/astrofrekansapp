"""Chat, attachment and device endpoints.

The contract, stated once so a client author does not have to infer it:

* **Sending** is a backend call. `POST /conversations/{id}/messages`.
* **Receiving** is a Firestore listener on
  `conversations/{firebase_conversation_id}/messages`, ordered by `createdAt`.
* **Presence and typing** are client writes to RTDB under the caller's own uid.
  The backend never writes them; it publishes the membership the rules consult.
* **Attachments** are: authorise here, upload straight to Storage, finalise
  here, then send a message referencing the attachment.

Everything owner-scoped answers `404` rather than `403`, so a wrong guess cannot
confirm that a conversation exists.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, UserRateLimit
from app.core.config import settings
from app.core.exceptions import NotFound
from app.db.models.chat import ExpertConversation, MediaAttachment, PushDevice
from app.db.models.marketplace import Expert
from app.db.models.user import User, UserProfile
from app.domain.chat import (
    AttachmentStatus,
    ConversationRole,
    ConversationStatus,
    DevicePlatform,
    ProvisioningStatus,
    PushCredential,
)
from app.schemas.chat import (
    AttachmentCreateRequest,
    AttachmentIntentResponse,
    AttachmentResponse,
    ChatPermissionResponse,
    ChatPolicyResponse,
    CloseConversationRequest,
    ConversationCreateRequest,
    ConversationResponse,
    ConversationSummary,
    DeviceRegisterRequest,
    DeviceResponse,
    VoipDeviceRegisterRequest,
    VoipDeviceResponse,
    MessagePageResponse,
    MessageResponse,
    MessageSendRequest,
    PresenceResponse,
    UploadGrantResponse,
)
from app.schemas.common import Message
from app.services.chat.attachments import AttachmentService
from app.services.chat.conversations import ConversationService
from app.services.chat.policy import describe_policy
from app.services.firebase.factory import firebase_available, get_firebase
from app.services.firebase.provider import FirebaseNotConfigured
from app.services.notifications.devices import DeviceService, mask_token
from app.services.notifications.outbox import OutboxService

router = APIRouter(tags=["chat"])

_conversation_limit = Depends(
    UserRateLimit(
        settings.conversation_create_rate_limit, scope="conversation_create"
    )
)
_message_limit = Depends(
    UserRateLimit(settings.message_send_rate_limit, scope="message_send")
)
_attachment_limit = Depends(
    UserRateLimit(
        settings.attachment_create_rate_limit, scope="attachment_create"
    )
)
_device_limit = Depends(
    UserRateLimit(settings.device_register_rate_limit, scope="device_register")
)


def _require_firebase() -> None:
    """Chat needs Firebase. A missing credential is a controlled 503."""
    if not firebase_available():
        raise FirebaseNotConfigured()


def _service(session) -> ConversationService:  # noqa: ANN001
    return ConversationService(session, get_firebase())


# ----------------------------------------------------------- serialisation


async def _counterpart_name(
    session, conversation: ExpertConversation, role: ConversationRole  # noqa: ANN001
) -> str | None:
    """Who the caller is talking to, as a display name.

    An expert's counterpart is a user, whose display name lives on their
    profile. A user's counterpart is an expert, whose display name is their
    public trading name - never the account behind it.
    """
    if role is ConversationRole.USER:
        expert = await session.scalar(
            select(Expert).where(Expert.id == conversation.expert_id)
        )
        return expert.display_name if expert else None

    # Read the profile column directly rather than through the relationship:
    # the user on the other side of the conversation is not the request's own
    # user, so nothing has loaded their profile, and touching a lazy
    # relationship here would attempt IO outside the async context.
    name = await session.scalar(
        select(UserProfile.name).where(
            UserProfile.user_id == conversation.user_id
        )
    )
    return (name or "").strip() or None


async def _conversation_to_schema(
    session,  # noqa: ANN001
    conversation: ExpertConversation,
    role: ConversationRole,
    permission,  # noqa: ANN001
) -> ConversationResponse:
    return ConversationResponse(
        id=conversation.id,
        order_id=conversation.order_id,
        appointment_id=conversation.appointment_id,
        status=ConversationStatus(conversation.status),
        provisioning_status=ProvisioningStatus(conversation.provisioning_status),
        my_role=role,
        counterpart_display_name=await _counterpart_name(
            session, conversation, role
        ),
        expert_id=conversation.expert_id,
        permission=ChatPermissionResponse(
            can_read=permission.can_read,
            can_write=permission.can_write,
            reason=permission.reason,
        ),
        firebase_conversation_id=conversation.firebase_conversation_id,
        message_count=conversation.message_count,
        last_message_at=conversation.last_message_at,
        closed_at=conversation.closed_at,
        created_at=conversation.created_at,
    )


def _message_to_schema(
    message, conversation_id: uuid.UUID  # noqa: ANN001
) -> MessageResponse:
    return MessageResponse(
        message_id=message.message_id,
        conversation_id=conversation_id,
        sender_role=message.sender_role,
        message_type=message.message_type,
        text=message.text,
        attachment_id=message.attachment_id,
        client_message_id=message.client_message_id,
        created_at=message.created_at,
        deleted_at=message.deleted_at,
    )


def _attachment_to_schema(attachment: MediaAttachment) -> AttachmentResponse:
    return AttachmentResponse(
        id=attachment.id,
        conversation_id=attachment.conversation_id,
        status=AttachmentStatus(attachment.status),
        mime_type=attachment.mime_type,
        verified_mime_type=attachment.verified_mime_type,
        size_bytes=attachment.size_bytes,
        original_filename=attachment.original_filename,
        storage_key=attachment.storage_key,
        rejection_reason=attachment.rejection_reason,
        created_at=attachment.created_at,
    )


def _voip_device_to_schema(device: PushDevice) -> VoipDeviceResponse:
    return VoipDeviceResponse(
        id=device.id,
        token_fingerprint=mask_token(device.token),
        environment=device.apns_environment or "",
        app_version=device.app_version,
        enabled=device.enabled,
        disabled_reason=device.disabled_reason,
        last_seen_at=device.last_seen_at,
        created_at=device.created_at,
    )


def _device_to_schema(device: PushDevice) -> DeviceResponse:
    return DeviceResponse(
        id=device.id,
        platform=DevicePlatform(device.platform),
        # The token itself is never returned: echoing it back would turn a
        # device list into a way to harvest push tokens.
        token_fingerprint=mask_token(device.token),
        app_version=device.app_version,
        enabled=device.enabled,
        disabled_reason=device.disabled_reason,
        last_seen_at=device.last_seen_at,
        created_at=device.created_at,
    )


# ------------------------------------------------------------------ policy


@router.get(
    "/chat/policy",
    response_model=ChatPolicyResponse,
    summary="When chat is allowed, and what a message may contain",
    description=(
        "The rules as data, so a client can explain a closed conversation "
        "without hard-coding the reasons."
    ),
)
async def chat_policy(user: CurrentUser) -> ChatPolicyResponse:
    policy = describe_policy()
    return ChatPolicyResponse(
        **policy,
        attachment_max_bytes=settings.attachment_max_bytes,
        attachment_allowed_mime_types=sorted(
            settings.allowed_attachment_mime_types
        ),
    )


# ----------------------------------------------------------- conversations


@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_conversation_limit],
    summary="Open the conversation for an order",
    description=(
        "Idempotent: one conversation per order is a database constraint, so a "
        "retry returns the original thread. Eligibility comes from the order "
        "and the service catalogue - a user cannot open a thread with an "
        "arbitrary expert."
    ),
)
async def create_conversation(
    payload: ConversationCreateRequest, user: CurrentUser, session: DbSession
) -> ConversationResponse:
    _require_firebase()
    service = _service(session)
    conversation = await service.ensure_for_order(user, payload.order_id)
    _, role, permission = await service.get_for_member(user, conversation.id)
    await session.commit()
    return await _conversation_to_schema(session, conversation, role, permission)


@router.get(
    "/conversations",
    response_model=list[ConversationSummary],
    summary="Your conversations",
    description="Threads the caller is in, on either side.",
)
async def list_conversations(
    user: CurrentUser,
    session: DbSession,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ConversationSummary]:
    _require_firebase()
    rows = await _service(session).list_for_user(user, limit=limit)

    summaries: list[ConversationSummary] = []
    for conversation in rows:
        role = (
            ConversationRole.USER
            if conversation.user_id == user.id
            else ConversationRole.EXPERT
        )
        summaries.append(
            ConversationSummary(
                id=conversation.id,
                order_id=conversation.order_id,
                status=ConversationStatus(conversation.status),
                my_role=role,
                counterpart_display_name=await _counterpart_name(
                    session, conversation, role
                ),
                message_count=conversation.message_count,
                last_message_at=conversation.last_message_at,
                created_at=conversation.created_at,
            )
        )
    return summaries


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
    summary="One conversation",
    description=(
        "Also reconciles the thread's status against its order, so a completed "
        "consultation becomes read-only without a scheduler."
    ),
)
async def get_conversation(
    conversation_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> ConversationResponse:
    _require_firebase()
    service = _service(session)
    conversation, role, permission = await service.get_for_member(
        user, conversation_id
    )
    await session.commit()
    return await _conversation_to_schema(session, conversation, role, permission)


@router.post(
    "/conversations/{conversation_id}/close",
    response_model=ConversationResponse,
    summary="Close a conversation to new messages",
    description="History survives. Either party may close.",
)
async def close_conversation(
    conversation_id: uuid.UUID,
    payload: CloseConversationRequest,
    user: CurrentUser,
    session: DbSession,
) -> ConversationResponse:
    _require_firebase()
    service = _service(session)
    conversation = await service.close(
        user, conversation_id, reason=payload.reason
    )
    _, role, permission = await service.get_for_member(user, conversation_id)
    await session.commit()
    return await _conversation_to_schema(session, conversation, role, permission)


# --------------------------------------------------------------- messages


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_message_limit],
    summary="Send a message",
    description=(
        "Messages are written by the backend, not by the client: authorisation "
        "depends on order state, expert suspension and a completion grace "
        "period, none of which Firestore rules can see. Receiving is still a "
        "Firestore listener.\n\n"
        "Send `client_message_id` and a retry returns the original message "
        "instead of posting a duplicate."
    ),
)
async def send_message(
    conversation_id: uuid.UUID,
    payload: MessageSendRequest,
    user: CurrentUser,
    session: DbSession,
) -> MessageResponse:
    _require_firebase()
    service = _service(session)

    message, conversation, role = await service.send_message(
        user,
        conversation_id,
        text=payload.text,
        attachment_id=payload.attachment_id,
        client_message_id=payload.client_message_id,
    )

    # The notification is queued in the same transaction as the message, so
    # there is no state where one happened and the other never will.
    recipient = await service.counterpart_user_id(conversation, user)
    await OutboxService(session).enqueue_chat_message(
        recipient_user_id=recipient,
        conversation_id=conversation.id,
        message_id=message.message_id,
    )

    await session.commit()
    return _message_to_schema(message, conversation.id)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=MessagePageResponse,
    summary="A page of history",
    description=(
        "Paginated on the server timestamp. Pass the previous page's "
        "`next_cursor` as `before`. A client listening for realtime updates "
        "only needs the newest page."
    ),
)
async def list_messages(
    conversation_id: uuid.UUID,
    user: CurrentUser,
    session: DbSession,
    limit: int = Query(default=50, ge=1, le=200),
    before: str | None = Query(default=None),
) -> MessagePageResponse:
    _require_firebase()
    messages, conversation = await _service(session).history(
        user, conversation_id, limit=limit, before=before
    )
    await session.commit()

    return MessagePageResponse(
        items=[_message_to_schema(item, conversation.id) for item in messages],
        next_cursor=messages[-1].created_at if messages else None,
        has_more=len(messages) == limit,
    )


@router.delete(
    "/conversations/{conversation_id}/messages/{message_id}",
    response_model=MessageResponse,
    summary="Delete your own message",
    description=(
        "Soft delete, and only the sender's own. An expert cannot remove a "
        "user's message and a user cannot remove an expert's - a conversation "
        "either party can edit is not a record of anything."
    ),
)
async def delete_message(
    conversation_id: uuid.UUID,
    message_id: str,
    user: CurrentUser,
    session: DbSession,
) -> MessageResponse:
    _require_firebase()
    message = await _service(session).delete_message(
        user, conversation_id, message_id
    )
    await session.commit()
    return _message_to_schema(message, conversation_id)


# --------------------------------------------------------------- presence


@router.get(
    "/conversations/{conversation_id}/presence",
    response_model=list[PresenceResponse],
    summary="Whether the other party is online",
    description=(
        "Only for people the caller shares this conversation with. There is no "
        "endpoint that reads presence by uid - a global presence lookup would "
        "let any account watch any other."
    ),
)
async def conversation_presence(
    conversation_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> list[PresenceResponse]:
    _require_firebase()
    service = _service(session)
    conversation, _, permission = await service.get_for_member(
        user, conversation_id
    )
    permission.require_read()
    await session.commit()

    firebase = get_firebase()
    rows = await session.execute(
        select(User.firebase_uid).where(
            User.id.in_([conversation.user_id, conversation.expert_user_id]),
            User.firebase_uid.is_not(None),
        )
    )

    states: list[PresenceResponse] = []
    for (uid,) in rows.all():
        state = await firebase.presence.read_presence(uid)
        states.append(
            PresenceResponse(
                firebase_uid=uid,
                online=state.online,
                last_changed=state.last_changed,
            )
        )
    return states


# ------------------------------------------------------------ attachments


@router.post(
    "/conversations/{conversation_id}/attachments",
    response_model=AttachmentIntentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_attachment_limit],
    summary="Authorise an attachment upload",
    description=(
        "Returns the one storage path this attachment may occupy. Upload "
        "directly to Firebase Storage, then call finalise. Until it is "
        "finalised the attachment cannot be attached to a message."
    ),
)
async def create_attachment(
    conversation_id: uuid.UUID,
    payload: AttachmentCreateRequest,
    user: CurrentUser,
    session: DbSession,
) -> AttachmentIntentResponse:
    _require_firebase()
    service = _service(session)
    conversation, _, permission = await service.get_for_member(
        user, conversation_id
    )
    # Uploading into a read-only thread would be writing to it.
    permission.require_write()

    attachments = AttachmentService(session, get_firebase())
    attachment, grant = await attachments.create_intent(
        user,
        conversation,
        mime_type=payload.mime_type,
        size_bytes=payload.size_bytes,
        original_filename=payload.original_filename,
    )
    await session.commit()

    return AttachmentIntentResponse(
        attachment=_attachment_to_schema(attachment),
        upload=UploadGrantResponse(
            storage_key=grant.storage_key,
            bucket=grant.bucket,
            max_bytes=grant.max_bytes,
            allowed_mime_types=grant.allowed_mime_types,
        ),
    )


@router.post(
    "/attachments/{attachment_id}/finalize",
    response_model=AttachmentResponse,
    summary="Confirm an upload arrived",
    description=(
        "Reads the stored object and checks it against what was promised. A "
        "type or size mismatch is rejected and the bytes are deleted - the "
        "claimed content type is not the content type."
    ),
)
async def finalize_attachment(
    attachment_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> AttachmentResponse:
    _require_firebase()

    # The attachment names its conversation; membership is then checked the
    # normal way, so this cannot be used to reach into another thread.
    row = await session.scalar(
        select(MediaAttachment).where(
            MediaAttachment.id == attachment_id,
            MediaAttachment.uploader_user_id == user.id,
        )
    )
    if row is None:
        raise NotFound("Attachment not found.")

    service = _service(session)
    conversation, _, permission = await service.get_for_member(
        user, row.conversation_id
    )
    permission.require_write()

    attachments = AttachmentService(session, get_firebase())
    finalised = await attachments.finalise(user, conversation, attachment_id)
    await session.commit()
    return _attachment_to_schema(finalised)


@router.get(
    "/conversations/{conversation_id}/attachments",
    response_model=list[AttachmentResponse],
    summary="Attachments shared in this conversation",
)
async def list_attachments(
    conversation_id: uuid.UUID,
    user: CurrentUser,
    session: DbSession,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[AttachmentResponse]:
    _require_firebase()
    service = _service(session)
    conversation, _, permission = await service.get_for_member(
        user, conversation_id
    )
    permission.require_read()

    attachments = AttachmentService(session, get_firebase())
    rows = await attachments.list_for_conversation(conversation, limit=limit)
    await session.commit()
    return [_attachment_to_schema(row) for row in rows]


# ---------------------------------------------------------------- devices


device_router = APIRouter(prefix="/devices", tags=["devices"])


@device_router.post(
    "/push",
    response_model=DeviceResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_device_limit],
    summary="Register this device for notifications",
    description=(
        "Idempotent on the token. Registering a token that belongs to another "
        "account moves it - a shared handset should not keep notifying the "
        "previous user."
    ),
)
async def register_device(
    payload: DeviceRegisterRequest, user: CurrentUser, session: DbSession
) -> DeviceResponse:
    device = await DeviceService(session).register(
        user,
        token=payload.token,
        platform=payload.platform,
        device_id=payload.device_id,
        app_version=payload.app_version,
    )
    await session.commit()
    return _device_to_schema(device)


@device_router.get(
    "/push",
    response_model=list[DeviceResponse],
    summary="Your registered devices",
    description="Tokens are never returned, only a fingerprint.",
)
async def list_devices(
    user: CurrentUser, session: DbSession
) -> list[DeviceResponse]:
    rows = await DeviceService(session).list_for_user(user)
    return [_device_to_schema(row) for row in rows]


@device_router.delete(
    "/push/{device_id}",
    response_model=Message,
    summary="Remove a device",
    description=(
        "A real delete rather than a flag: a token nobody should use is a token "
        "nobody should be able to read out of the database either."
    ),
)
async def delete_device(
    device_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> Message:
    await DeviceService(session).remove(user, device_id)
    await session.commit()
    return Message(message="Device removed.")


# -------------------------------------------------------------- VoIP (iOS)


@device_router.post(
    "/voip",
    response_model=VoipDeviceResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_device_limit],
    summary="Register this iPhone's PushKit VoIP token",
    description=(
        "A separate credential from the FCM token, used only to ring incoming "
        "calls through APNs (`apns-push-type: voip`) and CallKit. Idempotent on "
        "the token; a token registered from another account moves. The token "
        "is never returned."
    ),
)
async def register_voip_device(
    payload: VoipDeviceRegisterRequest, user: CurrentUser, session: DbSession
) -> VoipDeviceResponse:
    device = await DeviceService(session).register_voip(
        user,
        token=payload.token,
        environment=payload.environment,
        device_id=payload.device_id,
        app_version=payload.app_version,
    )
    await session.commit()
    return _voip_device_to_schema(device)


@device_router.get(
    "/voip",
    response_model=list[VoipDeviceResponse],
    summary="Your registered VoIP credentials",
)
async def list_voip_devices(
    user: CurrentUser, session: DbSession
) -> list[VoipDeviceResponse]:
    rows = await DeviceService(session).list_for_user(
        user, credential=PushCredential.APNS_VOIP
    )
    return [_voip_device_to_schema(row) for row in rows]


@device_router.delete(
    "/voip/{device_id}",
    response_model=Message,
    summary="Remove a VoIP credential",
    description=(
        "Call on sign-out and when PushKit invalidates the token "
        "(`didInvalidatePushTokenFor`). Another user's id is 404."
    ),
)
async def delete_voip_device(
    device_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> Message:
    await DeviceService(session).remove(
        user, device_id, credential=PushCredential.APNS_VOIP
    )
    await session.commit()
    return Message(message="Device removed.")

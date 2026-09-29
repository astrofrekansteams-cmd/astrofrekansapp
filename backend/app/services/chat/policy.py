"""When chat is allowed, and by whom.

All of it lives here rather than as `if` statements scattered through routes,
because this is the kind of rule that gets copied and then diverges: one
endpoint would keep letting a cancelled order write messages long after
another stopped.

Two separate questions, deliberately:

* **May they read the history?** A finished consultation somebody paid for is
  theirs to scroll back through.
* **May they write a new message?** That stops when the engagement does.

Collapsing the two would mean either a cancelled order stays a live chat, or a
user loses the record of what they were told.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.core.config import settings
from app.core.exceptions import AppError
from app.db.models.chat import ExpertConversation
from app.db.models.marketplace import Expert, ServiceOrder
from app.db.models.service import ServiceDefinition
from app.domain.chat import ConversationStatus
from app.domain.marketplace import (
    DeliveryType,
    ExpertStatus,
    FulfillmentMode,
    OrderStatus,
)


class ChatNotAvailable(AppError):
    status_code = 409
    code = "chat_not_available"
    message = "Chat is not available for this order."


class ChatReadOnly(AppError):
    status_code = 409
    code = "chat_read_only"
    message = "This conversation is closed to new messages."


# Order states in which a conversation may be opened and written to. Notably
# absent: `pending_payment`. Chat before payment would be a free consultation
# channel, which is not what anybody agreed to.
WRITABLE_ORDER_STATES = frozenset(
    {
        OrderStatus.PAID.value,
        OrderStatus.CONFIRMED.value,
        OrderStatus.AWAITING_EXPERT.value,
        OrderStatus.IN_PROGRESS.value,
    }
)

# States where the history stays available but nothing new may be written.
READABLE_ORDER_STATES = WRITABLE_ORDER_STATES | frozenset(
    {
        OrderStatus.COMPLETED.value,
        OrderStatus.CANCELLED.value,
        OrderStatus.REFUNDED.value,
    }
)

# Channels that imply a text conversation. A written report is delivered, not
# discussed, so it does not open a chat on its own.
CHAT_DELIVERY_TYPES = frozenset(
    {DeliveryType.CHAT.value, DeliveryType.VOICE.value, DeliveryType.VIDEO.value}
)


@dataclass(slots=True, frozen=True)
class ChatPermission:
    """What this caller may do with this conversation, and why."""

    can_read: bool
    can_write: bool
    reason: str

    def require_read(self) -> None:
        if not self.can_read:
            raise ChatNotAvailable(details={"reason": self.reason})

    def require_write(self) -> None:
        self.require_read()
        if not self.can_write:
            raise ChatReadOnly(details={"reason": self.reason})


def order_allows_new_conversation(
    order: ServiceOrder, definition: ServiceDefinition
) -> tuple[bool, str]:
    """Whether this order entitles anybody to a chat thread at all.

    Eligibility comes from the B8 catalogue and order, not from a client asking
    nicely: a user cannot open a thread with an arbitrary expert.
    """
    if order.expert_id is None:
        return False, "order_has_no_expert"

    mode = order.fulfillment_mode
    if mode not in (FulfillmentMode.EXPERT.value, FulfillmentMode.HYBRID.value):
        return False, "order_is_automated"

    # The channel sold must be a conversational one, and the catalogue must
    # actually support chat for it.
    if order.delivery_type not in CHAT_DELIVERY_TYPES:
        return False, "delivery_type_has_no_chat"
    if not definition.supports_chat:
        return False, "service_does_not_support_chat"

    if order.status not in WRITABLE_ORDER_STATES:
        return False, f"order_state_{order.status}"

    return True, "eligible"


def conversation_status_for_order(order: ServiceOrder) -> ConversationStatus:
    """The status a conversation should have, given its order's state.

    Pure, so reconciliation and creation cannot disagree about it.
    """
    if order.status in WRITABLE_ORDER_STATES:
        return ConversationStatus.ACTIVE

    if order.status == OrderStatus.COMPLETED.value:
        # A grace period, then read-only. Somebody who has just been told
        # something complicated will have a follow-up question.
        if order.completed_at is None:
            return ConversationStatus.ACTIVE
        grace = timedelta(days=settings.chat_read_only_after_completion_days)
        completed = order.completed_at
        if completed.tzinfo is None:
            completed = completed.replace(tzinfo=UTC)
        if datetime.now(UTC) - completed <= grace:
            return ConversationStatus.ACTIVE
        return ConversationStatus.READ_ONLY

    if order.status in (
        OrderStatus.CANCELLED.value,
        OrderStatus.REFUNDED.value,
    ):
        return ConversationStatus.READ_ONLY

    return ConversationStatus.CLOSED


def permission_for(
    conversation: ExpertConversation,
    order: ServiceOrder,
    *,
    expert: Expert | None,
) -> ChatPermission:
    """What the caller may do, combining every relevant fact.

    Read access survives almost everything; write access is narrow.

    Deliberately **not** parameterised by which side is asking: every condition
    that closes a thread closes it for both parties. An expert who may not write
    and a user with nobody to write to are the same situation, and a permission
    function that could answer differently per side is one that will eventually
    let one of them speak into a thread the other cannot.
    """
    status = ConversationStatus(conversation.status)

    if status is ConversationStatus.SUSPENDED:
        # Moderation. Neither side reads or writes while a thread is suspended.
        return ChatPermission(False, False, "conversation_suspended")

    can_read = order.status in READABLE_ORDER_STATES
    if not can_read:
        return ChatPermission(False, False, f"order_state_{order.status}")

    if not status.allows_write:
        return ChatPermission(True, False, f"conversation_{status.value}")

    # Derived, not re-checked. `conversation_status_for_order` is the one place
    # that knows the post-completion grace period exists; testing
    # `order.status not in WRITABLE_ORDER_STATES` here instead - as an earlier
    # version did - silently cancelled it, because `completed` is never a
    # writable order state.
    if not conversation_status_for_order(order).allows_write:
        return ChatPermission(True, False, f"order_state_{order.status}")

    # A suspended expert ends the conversation for both sides - the user has
    # nobody to talk to - but both keep their history. It is evidence of what
    # was said, and withdrawing it would punish the wrong person.
    if expert is not None and expert.status == ExpertStatus.SUSPENDED.value:
        return ChatPermission(True, False, "expert_suspended")

    return ChatPermission(True, True, "ok")


def effective_status(
    conversation: ExpertConversation, order: ServiceOrder
) -> ConversationStatus:
    """The status `ConversationService._reconcile` would settle on. Pure.

    Moderation outranks order state, and a thread one of the parties closed
    stays closed; anything else follows its order - so a stored status that
    has not been read since its order moved on is not trusted as-is.
    """
    current = ConversationStatus(conversation.status)
    if current is ConversationStatus.SUSPENDED:
        return current
    if current is ConversationStatus.CLOSED and conversation.closed_at:
        return current
    return conversation_status_for_order(order)


def grants_presence(
    conversation: ExpertConversation,
    order: ServiceOrder,
    *,
    expert: Expert | None,
) -> bool:
    """Whether the two members may see each other's presence.

    The single presence rule: `ConversationService.provision` publishes or
    revokes by it, and the backfill command rebuilds by it, so the two cannot
    disagree.

    A closed thread grants nothing, judged on the settled status rather than a
    possibly stale stored one; beyond that, `permission_for`'s read access
    decides - a suspended thread, or one whose order no longer entitles anybody
    to it, grants nothing.

    Current product policy: a READ_ONLY thread (post-completion grace over, or
    a cancelled/refunded order) still grants presence. Changing that is a
    product decision, not a fix.
    """
    if conversation.deleted_at is not None or order.deleted_at is not None:
        return False
    if effective_status(conversation, order) is ConversationStatus.CLOSED:
        return False
    return permission_for(conversation, order, expert=expert).can_read


def describe_policy() -> dict:
    """The policy as data, for the API and the docs to agree on."""
    return {
        "writable_order_states": sorted(WRITABLE_ORDER_STATES),
        "readable_order_states": sorted(READABLE_ORDER_STATES),
        "chat_delivery_types": sorted(CHAT_DELIVERY_TYPES),
        "read_only_after_completion_days": (
            settings.chat_read_only_after_completion_days
        ),
        "message_max_length": settings.chat_message_max_length,
        "attachments_per_message": settings.chat_attachments_per_message,
    }

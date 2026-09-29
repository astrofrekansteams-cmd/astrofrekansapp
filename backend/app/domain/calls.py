"""Voice and video calls: the vocabulary and the state machine.

The state machine lives here, as data, so there is exactly one answer to "may a
call go from X to Y". Routes never assign a status; they ask the lifecycle
service, which asks `can_transition`. A status written from three places is a
status that eventually disagrees with itself.

Text chat is **not** a call type. It stays in the B9 conversation domain, and
nothing here carries messages.
"""

from __future__ import annotations

from enum import StrEnum


class CallType(StrEnum):
    AUDIO = "audio"
    VIDEO = "video"


class CallStatus(StrEnum):
    """Where a call is in its life.

    * SCHEDULED - created before its join window opened. No room yet.
    * WAITING   - the room exists; nobody has joined.
    * RINGING   - one party is in the room and the other has been notified.
    * ACTIVE    - both parties have been in the room at the same time.
    * ENDED     - finished, whether it ever became active or not.
    * MISSED    - one party waited out the ring timeout alone.
    * CANCELLED - withdrawn before it became active, or its appointment was.
    * FAILED    - the room could not be provisioned.

    The last four are terminal. A terminal call never becomes live again; a new
    consultation attempt is a new session, which is what keeps the audit trail
    of each attempt intact.
    """

    SCHEDULED = "scheduled"
    WAITING = "waiting"
    RINGING = "ringing"
    ACTIVE = "active"
    ENDED = "ended"
    MISSED = "missed"
    CANCELLED = "cancelled"
    FAILED = "failed"

    @property
    def is_terminal(self) -> bool:
        return self in TERMINAL_STATUSES

    @property
    def is_live(self) -> bool:
        return not self.is_terminal


TERMINAL_STATUSES = frozenset(
    {CallStatus.ENDED, CallStatus.MISSED, CallStatus.CANCELLED, CallStatus.FAILED}
)
LIVE_STATUSES = frozenset(set(CallStatus) - TERMINAL_STATUSES)

# The whole machine. Anything not listed is refused.
TRANSITIONS: dict[CallStatus, frozenset[CallStatus]] = {
    CallStatus.SCHEDULED: frozenset(
        {CallStatus.WAITING, CallStatus.CANCELLED, CallStatus.FAILED, CallStatus.ENDED}
    ),
    CallStatus.WAITING: frozenset(
        {
            CallStatus.RINGING,
            # Both joined before a webhook for the first one arrived.
            CallStatus.ACTIVE,
            CallStatus.CANCELLED,
            CallStatus.ENDED,
            CallStatus.FAILED,
        }
    ),
    CallStatus.RINGING: frozenset(
        {
            CallStatus.ACTIVE,
            CallStatus.MISSED,
            CallStatus.CANCELLED,
            # The caller gave up and the window closed around them.
            CallStatus.ENDED,
            # The lone party left and did not come back: nobody is waiting.
            CallStatus.WAITING,
        }
    ),
    CallStatus.ACTIVE: frozenset({CallStatus.ENDED}),
    CallStatus.ENDED: frozenset(),
    CallStatus.MISSED: frozenset(),
    CallStatus.CANCELLED: frozenset(),
    CallStatus.FAILED: frozenset(),
}


def can_transition(current: CallStatus, target: CallStatus) -> bool:
    return target in TRANSITIONS[current]


class ParticipantRole(StrEnum):
    USER = "user"
    EXPERT = "expert"


class ParticipantStatus(StrEnum):
    """One party's relationship to the room.

    Deliberately coarse. Microphone and camera state are the client SDK's
    business and are never written here - an audit trail of every mute is
    noise, and a record of when somebody turned their camera off is not
    something anybody asked us to keep.
    """

    INVITED = "invited"  # a participant row exists; no token issued yet
    JOINING = "joining"  # a token was issued; the provider has not seen them
    JOINED = "joined"  # the provider says they are in the room
    LEFT = "left"  # left on purpose (the client disconnected)
    DISCONNECTED = "disconnected"  # dropped; may reconnect within the grace


PRESENT = frozenset({ParticipantStatus.JOINED})


class CallEndReason(StrEnum):
    """Why a call stopped. Stored for a future refund policy; B10 decides none."""

    USER_ENDED = "user_ended"
    EXPERT_ENDED = "expert_ended"
    MISSED = "missed"
    # The window closed or the hard ceiling was reached.
    TIMEOUT = "timeout"
    PROVIDER_ERROR = "provider_error"
    # A party dropped and did not return within the reconnect grace.
    NETWORK_DISCONNECT = "network_disconnect"
    APPOINTMENT_CANCELLED = "appointment_cancelled"
    ORDER_CANCELLED = "order_cancelled"
    EXPERT_SUSPENDED = "expert_suspended"
    # Nobody joined before the window closed.
    NO_SHOW = "no_show"
    SYSTEM = "system"


class ProviderEventType(StrEnum):
    """LiveKit webhook events, by their documented names."""

    ROOM_STARTED = "room_started"
    ROOM_FINISHED = "room_finished"
    PARTICIPANT_JOINED = "participant_joined"
    PARTICIPANT_LEFT = "participant_left"
    PARTICIPANT_CONNECTION_ABORTED = "participant_connection_aborted"
    TRACK_PUBLISHED = "track_published"
    TRACK_UNPUBLISHED = "track_unpublished"
    OTHER = "other"

    @classmethod
    def parse(cls, value: str) -> "ProviderEventType":
        try:
            return cls(value)
        except ValueError:
            return cls.OTHER


# Track sources a participant may publish, by call type. These are LiveKit's
# `canPublishSources` values, verified against the SDK - a source not listed
# cannot be published, so an audio consultation cannot turn a camera on however
# the client is modified. Screen sharing is in neither list.
PUBLISH_SOURCES: dict[CallType, tuple[str, ...]] = {
    CallType.AUDIO: ("microphone",),
    CallType.VIDEO: ("camera", "microphone"),
}

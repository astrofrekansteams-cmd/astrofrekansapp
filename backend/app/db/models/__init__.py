"""ORM models.

Imported for their side effect: Alembic autogenerate and ``Base.metadata``
need every model registered.
"""

from app.db.models.ai import (
    AIConversation,
    AIGeneration,
    AIMessage,
    AIReport,
    AIReportJob,
)
from app.db.models.birth_profile import BirthProfile, SavedPerson
from app.db.models.calls import CallParticipant, CallProviderEvent, CallSession
from app.db.models.chart import ChartCache
from app.db.models.chat import (
    ExpertConversation,
    FirebaseIdentityRecord,
    MediaAttachment,
    NotificationDelivery,
    NotificationOutbox,
    PushDevice,
)
from app.db.models.coins import CoinTransaction, CoinWallet
from app.db.models.compatibility import CompatibilityReport
from app.db.models.divination import (
    DivinationDrawItem,
    DivinationDrawSession,
    DivinationReading,
)
from app.db.models.marketplace import (
    Appointment,
    Expert,
    ExpertAvailability,
    ExpertAvailabilityException,
    ExpertFavorite,
    ExpertReview,
    ExpertService,
    ServiceConsent,
    ServiceOrder,
    ServiceOrderSource,
    SlotHold,
)
from app.db.models.horary import HoraryAnalysisRecord, HoraryQuestion
from app.db.models.payments import (
    ExpertPayout,
    LedgerEntry,
    OrderLineItem,
    OrderPaymentGroup,
    PaymentIntent,
    PaymentProviderEvent,
    PaymentTransaction,
    RefundRequest,
    StoreProduct,
    StorePurchase,
    UserEntitlement,
)
from app.db.models.forecast import CosmicEventRecord, ForecastSnapshot
from app.db.models.service import ServiceDefinition
from app.db.models.subscription import Subscription
from app.db.models.token import PasswordResetToken, RefreshToken
from app.db.models.user import User, UserProfile

__all__ = [
    "AIConversation",
    "AIGeneration",
    "AIMessage",
    "AIReport",
    "AIReportJob",
    "BirthProfile",
    "CallParticipant",
    "CallProviderEvent",
    "CallSession",
    "ChartCache",
    "CompatibilityReport",
    "ExpertConversation",
    "FirebaseIdentityRecord",
    "MediaAttachment",
    "NotificationDelivery",
    "NotificationOutbox",
    "PushDevice",
    "DivinationDrawItem",
    "DivinationDrawSession",
    "DivinationReading",
    "Appointment",
    "Expert",
    "ExpertAvailability",
    "ExpertAvailabilityException",
    "CoinTransaction",
    "CoinWallet",
    "ExpertFavorite",
    "ExpertReview",
    "ExpertService",
    "ServiceConsent",
    "ServiceOrder",
    "ServiceOrderSource",
    "SlotHold",
    "HoraryAnalysisRecord",
    "ExpertPayout",
    "LedgerEntry",
    "OrderLineItem",
    "OrderPaymentGroup",
    "PaymentIntent",
    "PaymentProviderEvent",
    "PaymentTransaction",
    "RefundRequest",
    "StoreProduct",
    "StorePurchase",
    "UserEntitlement",
    "HoraryQuestion",
    "CosmicEventRecord",
    "ForecastSnapshot",
    "PasswordResetToken",
    "RefreshToken",
    "SavedPerson",
    "ServiceDefinition",
    "Subscription",
    "User",
    "UserProfile",
]

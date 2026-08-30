from .audit_logs import AuditLog
from .chat import ChatMessage, ChatSession, UsageCounter
from .compliance import ComplianceDisclosure, ComplianceGroup, DisclosureType
from .insights import Insight, MarketInsightReview
from .notifications import Notification, NotificationAudience, UserNotificationRead
from .onboarding_questioner import (
    OnboardingQuestion,
    OnboardingQuestionOption,
    TierOnboardingQuestion,
    UserOnboardingAnswer,
)
from .scraping import IngestedPDF, ScrapingURL
from .signals import Signal, SignalStatus, SignalType
from .subscriptions import (
    Subscription,
    SubscriptionChange,
    SubscriptionSource,
    SubscriptionStatus,
)
from .tiers import Entitlements, Tier, TierEntitlement
from .tokens import (
    DailyTokenUsage,
    TierTokenConfig,
    TokenTransactions,
    UserTokenWallets,
)
from .users import (
    Role,
    User,
    UserProfile,
    UserRole,
    UserSession,
    UserStatus,
    VisitingUser,
)

# Re-exported so importing any single model also imports every other model class,
# registering all of them on the shared declarative Base before Base.metadata.create_all()
# runs (see app/main.py) - not just a convenience import.
__all__ = [
    "AuditLog",
    "ChatMessage",
    "ChatSession",
    "UsageCounter",
    "ComplianceDisclosure",
    "ComplianceGroup",
    "DisclosureType",
    "Insight",
    "MarketInsightReview",
    "Notification",
    "NotificationAudience",
    "UserNotificationRead",
    "OnboardingQuestion",
    "OnboardingQuestionOption",
    "TierOnboardingQuestion",
    "UserOnboardingAnswer",
    "IngestedPDF",
    "ScrapingURL",
    "Signal",
    "SignalStatus",
    "SignalType",
    "Subscription",
    "SubscriptionChange",
    "SubscriptionSource",
    "SubscriptionStatus",
    "Entitlements",
    "Tier",
    "TierEntitlement",
    "DailyTokenUsage",
    "TierTokenConfig",
    "TokenTransactions",
    "UserTokenWallets",
    "Role",
    "User",
    "UserProfile",
    "UserRole",
    "UserSession",
    "UserStatus",
    "VisitingUser",
]

"""SQLAlchemy models grouped by backend domain."""

from .clients import (
    ClientActivityEvent,
    ClientProfile,
    ClientTrafficSample,
    NetworkClient,
)
from .commands import DeviceCommand, TerminalFrame, TerminalSession
from .devices import Device, DeviceGroup
from .hardware import DeviceHardwareIdentity, HardwareProfile, HardwareSensorSample
from .identity import (
    AppSetting,
    AuthAttempt,
    MobilePairingAttempt,
    MobilePairingToken,
    User,
    UserSession,
)
from .operations import (
    AuditLog,
    AutomationRule,
    AutomationRun,
    EventRecord,
    FeedbackRecord,
    NotificationRule,
)
from .telemetry import DeviceTelemetry, DeviceTelemetryMetric

__all__ = [
    "AppSetting",
    "AuditLog",
    "AuthAttempt",
    "AutomationRule",
    "AutomationRun",
    "ClientActivityEvent",
    "ClientProfile",
    "ClientTrafficSample",
    "Device",
    "DeviceCommand",
    "DeviceGroup",
    "DeviceHardwareIdentity",
    "DeviceTelemetry",
    "DeviceTelemetryMetric",
    "EventRecord",
    "FeedbackRecord",
    "HardwareProfile",
    "HardwareSensorSample",
    "MobilePairingAttempt",
    "MobilePairingToken",
    "NetworkClient",
    "NotificationRule",
    "TerminalFrame",
    "TerminalSession",
    "User",
    "UserSession",
]

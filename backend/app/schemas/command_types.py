from __future__ import annotations

from typing import Literal, TypeAlias, TypedDict

from pydantic import JsonValue


CommandPayload: TypeAlias = dict[str, JsonValue]
CommandResult: TypeAlias = dict[str, JsonValue]
CommandResultStatus: TypeAlias = Literal["running", "done", "success", "failed"]


class DeliveryPolicy(TypedDict):
    timeout_seconds: int
    lease_seconds: int
    max_deliveries: int


class IdempotencyPolicy(TypedDict):
    strategy: str
    semantic: bool


class VerificationPolicy(TypedDict):
    required: bool
    mode: str
    fail_closed: bool


class ReliabilityPolicy(TypedDict):
    subsystem: str
    idempotency: IdempotencyPolicy
    delivery: DeliveryPolicy
    post_condition: str
    verification: VerificationPolicy
    rollback: str

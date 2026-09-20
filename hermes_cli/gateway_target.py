"""Frozen value contract for a trusted gateway canary target.

This import-safe module intentionally contains no issuer, validator, staging, registration,
callback, clock, nonce, store, or delivery authority.  Direct construction creates only a value;
it is not gateway attestation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


_TARGET_ERROR = "invalid trusted gateway canary target"
_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _canonical_string(value: Any) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(_TARGET_ERROR)
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in value):
        raise ValueError(_TARGET_ERROR)
    return value


def _canonical_utc(value: Any) -> str:
    value = _canonical_string(value)
    try:
        parsed = datetime.strptime(value, _TIMESTAMP_FORMAT).replace(tzinfo=UTC)
    except (TypeError, ValueError) as exc:
        raise ValueError(_TARGET_ERROR) from exc
    if parsed.strftime(_TIMESTAMP_FORMAT) != value:
        raise ValueError(_TARGET_ERROR)
    return value


@dataclass(frozen=True, slots=True, repr=False)
class TrustedGatewayCanaryTarget:
    """Immutable target value; construction alone grants no trust or delivery authority."""

    platform: str
    adapter_id: str
    chat_id: str
    user_id: str
    session_id: str
    nonce: str
    issued_at_utc: str

    def __post_init__(self) -> None:
        for name in ("platform", "adapter_id", "chat_id", "user_id", "session_id", "nonce"):
            _canonical_string(getattr(self, name))
        _canonical_utc(self.issued_at_utc)

    def __repr__(self) -> str:
        return "TrustedGatewayCanaryTarget(<redacted>)"

    __str__ = __repr__


__all__ = ["TrustedGatewayCanaryTarget"]

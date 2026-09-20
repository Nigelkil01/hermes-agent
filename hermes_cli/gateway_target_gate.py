"""Fail-closed delivery boundary for the deferred trusted gateway target contract."""

from __future__ import annotations

from typing import Any


def deliver_runtime_issued_target(value: Any) -> None:
    """Accept and disclose nothing until gateway-owned issuance is implemented."""
    return None


__all__: list[str] = []

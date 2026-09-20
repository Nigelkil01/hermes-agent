"""Blocked trusted gateway target activation boundary.

Story 2 remains fail-closed until a separately reviewed, gateway-private verifier is
designed around a real authenticated ingress source.  This module intentionally exposes
no issuer, verifier, envelope, binding, carrier, consume/take/discard helper, or hook
delivery API.  :class:`hermes_cli.gateway_target.TrustedGatewayCanaryTarget` remains only
an immutable redacted value contract; direct construction never grants authority.
"""

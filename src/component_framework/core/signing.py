"""HMAC-SHA256 signing for client-carried component state.

Component state round-trips through the client on every dispatch. Without a
signature, the client can tamper with any state field before echoing it back.
This module signs outbound state and verifies inbound state at the
:class:`~component_framework.core.component.StateSerializer` choke point, so
every adapter (FastAPI, Flask, Litestar, Django, WebSocket) is covered.

Token format (version ``cfs1``)::

    cfs1.<base64url_nopad(json_payload)>.<base64url_nopad(hmac_sha256_mac)>

The MAC covers ``b"cfs1." + payload_b64`` so a token can never be confused
with (or replayed into) a future format version.

Enable signing by calling :meth:`StateSigner.configure` at application start,
or by setting the ``STATE_SIGNING_KEY`` environment variable. Both accept
multiple keys for rotation (a sequence for ``configure``, comma-separated for
the env var): the FIRST key signs new tokens, ALL keys verify inbound tokens.

Uses only the standard library (hmac, hashlib, base64, os).
"""

import base64
import binascii
import hashlib
import hmac
import logging
import os
from collections.abc import Sequence
from typing import ClassVar

from .component import ComponentError

logger = logging.getLogger(__name__)

ENV_VAR = "STATE_SIGNING_KEY"
TOKEN_VERSION = "cfs1"

SecretInput = str | bytes | Sequence[str | bytes] | None


class CorruptStateError(ComponentError):
    """Raised when inbound state fails signature verification.

    Covers tampered payloads, tampered/invalid MACs, malformed or truncated
    tokens, unsigned input (plain JSON or raw dicts) while signing is
    enabled, and tokens signed with an unknown key.
    """


def _b64url_encode(data: bytes) -> str:
    """Encode bytes as unpadded URL-safe base64."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    """Decode unpadded URL-safe base64 back to bytes."""
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


class StateSigner:
    """HMAC-SHA256 signer/verifier for serialized component state.

    Key resolution order:
        1. Keys set via :meth:`configure` (including an explicit ``None`` to
           disable signing regardless of the environment).
        2. The ``STATE_SIGNING_KEY`` environment variable (comma-separated
           values enable rotation).
        3. Nothing configured: signing is disabled (legacy pass-through) and
           a one-time warning is logged on first serialization.

    Rotation: the first key signs, all keys verify. To rotate, prepend the
    new key, keep the old key until in-flight client states have expired,
    then drop it.
    """

    _keys: ClassVar[tuple[bytes, ...] | None] = None
    _configured: ClassVar[bool] = False
    _warned_unsigned: ClassVar[bool] = False

    # ---------- Configuration ----------

    @classmethod
    def configure(cls, secret: SecretInput) -> None:
        """Configure signing keys.

        Args:
            secret: A single key (``str`` or ``bytes``), a sequence of keys
                for rotation (first signs, all verify), or ``None`` to
                explicitly disable signing (overrides the environment
                variable).

        Raises:
            ValueError: If a key is empty or an empty sequence is given.
        """
        cls._keys = None if secret is None else cls._normalize(secret)
        cls._configured = True
        cls._warned_unsigned = False

    @classmethod
    def reset(cls) -> None:
        """Reset to the unconfigured default (env-var fallback).

        Intended for tests and application teardown.
        """
        cls._keys = None
        cls._configured = False
        cls._warned_unsigned = False

    @classmethod
    def enabled(cls) -> bool:
        """Return True when at least one signing key is available."""
        return bool(cls._resolve_keys())

    @classmethod
    def _normalize(cls, secret: str | bytes | Sequence[str | bytes]) -> tuple[bytes, ...]:
        """Normalize a secret (or sequence of secrets) into key bytes."""
        raw: Sequence[str | bytes]
        raw = [secret] if isinstance(secret, (str, bytes)) else list(secret)
        if not raw:
            raise ValueError("StateSigner.configure() requires at least one signing key")
        keys: list[bytes] = []
        for item in raw:
            key = item.encode("utf-8") if isinstance(item, str) else bytes(item)
            if not key:
                raise ValueError("Signing keys must be non-empty")
            keys.append(key)
        return tuple(keys)

    @classmethod
    def _resolve_keys(cls) -> tuple[bytes, ...] | None:
        """Resolve active keys from explicit config or the environment."""
        if cls._configured:
            return cls._keys
        env_value = os.environ.get(ENV_VAR, "")
        parts = [part.strip() for part in env_value.split(",") if part.strip()]
        if not parts:
            return None
        return tuple(part.encode("utf-8") for part in parts)

    # ---------- Signing / verification ----------

    @classmethod
    def sign(cls, payload_json: str) -> str:
        """Sign a JSON payload string into a ``cfs1`` token.

        Args:
            payload_json: The serialized (JSON) state to protect.

        Returns:
            A ``cfs1.<payload_b64>.<mac_b64>`` token string.

        Raises:
            ComponentError: If no signing key is configured.
        """
        keys = cls._resolve_keys()
        if not keys:
            raise ComponentError("StateSigner.sign() called but no signing key is configured")
        payload_b64 = _b64url_encode(payload_json.encode("utf-8"))
        mac = hmac.new(keys[0], cls._signing_input(payload_b64), hashlib.sha256).digest()
        return f"{TOKEN_VERSION}.{payload_b64}.{_b64url_encode(mac)}"

    @classmethod
    def verify(cls, token: str) -> str:
        """Verify a ``cfs1`` token and return the embedded JSON payload.

        All configured keys are tried (rotation support), using
        :func:`hmac.compare_digest` for constant-time comparison.

        Args:
            token: The inbound token string.

        Returns:
            The verified JSON payload string.

        Raises:
            CorruptStateError: If the token is malformed, unsigned, tampered
                with, or signed with an unknown key.
            ComponentError: If no signing key is configured.
        """
        keys = cls._resolve_keys()
        if not keys:
            raise ComponentError("StateSigner.verify() called but no signing key is configured")

        if not isinstance(token, str):
            raise CorruptStateError(
                f"Signed state token must be a string, got {type(token).__name__}"
            )

        parts = token.split(".")
        if len(parts) != 3 or parts[0] != TOKEN_VERSION:
            raise CorruptStateError("State token is malformed or unsigned")
        _, payload_b64, mac_b64 = parts

        try:
            provided_mac = _b64url_decode(mac_b64)
        except (binascii.Error, ValueError) as e:
            raise CorruptStateError("State token MAC is not valid base64") from e

        signing_input = cls._signing_input(payload_b64)
        for key in keys:
            expected_mac = hmac.new(key, signing_input, hashlib.sha256).digest()
            if hmac.compare_digest(expected_mac, provided_mac):
                try:
                    return _b64url_decode(payload_b64).decode("utf-8")
                except (binascii.Error, ValueError, UnicodeDecodeError) as e:
                    raise CorruptStateError("State token payload is not decodable") from e

        raise CorruptStateError("State signature verification failed")

    @staticmethod
    def _signing_input(payload_b64: str) -> bytes:
        """Build the MAC input, binding the version prefix to the payload."""
        return f"{TOKEN_VERSION}.{payload_b64}".encode("ascii")

    # ---------- Diagnostics ----------

    @classmethod
    def warn_unsigned_once(cls) -> None:
        """Log a one-time prominent warning that state is unsigned."""
        if cls._warned_unsigned:
            return
        cls._warned_unsigned = True
        logger.warning(
            "SECURITY: component state signing is DISABLED — client-carried "
            "state is unsigned and can be tampered with. Set the "
            "%s environment variable or call StateSigner.configure() "
            "with a secret key before deploying to production.",
            ENV_VAR,
        )

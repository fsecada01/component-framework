"""Tests for HMAC state signing (Epic A, task A1)."""

import base64
import json
import logging

import pytest

from component_framework.core.component import ComponentError, StateSerializer
from component_framework.core.signing import CorruptStateError, StateSigner


@pytest.fixture(autouse=True)
def _reset_signer(monkeypatch):
    """Isolate signer configuration per test (env + class state)."""
    monkeypatch.delenv("STATE_SIGNING_KEY", raising=False)
    StateSigner.reset()
    yield
    StateSigner.reset()


# ---------- Basic sign/verify ----------


class TestSignVerifyRoundTrip:
    def test_round_trip_preserves_state(self):
        StateSigner.configure("secret-key")
        state = {"count": 3, "name": "widget", "nested": {"a": [1, 2]}}
        token = StateSerializer.serialize(state)
        assert token.startswith("cfs1.")
        assert StateSerializer.deserialize(token) == state

    def test_token_has_three_segments(self):
        StateSigner.configure("secret-key")
        token = StateSerializer.serialize({"x": 1})
        assert len(token.split(".")) == 3

    def test_empty_state_round_trip(self):
        StateSigner.configure("secret-key")
        token = StateSerializer.serialize({})
        assert token.startswith("cfs1.")
        assert StateSerializer.deserialize(token) == {}

    def test_corrupt_state_error_is_component_error(self):
        assert issubclass(CorruptStateError, ComponentError)


# ---------- Tampering ----------


class TestTamperRejection:
    def _make_token(self, state: dict) -> str:
        StateSigner.configure("secret-key")
        return StateSerializer.serialize(state)

    def test_tampered_payload_rejected(self):
        token = self._make_token({"count": 1})
        version, _payload, mac = token.split(".")
        # Substitute a different (validly encoded) payload, keep the old MAC.
        forged_payload = (
            base64.urlsafe_b64encode(json.dumps({"count": 999}).encode()).rstrip(b"=").decode()
        )
        forged = f"{version}.{forged_payload}.{mac}"
        with pytest.raises(CorruptStateError):
            StateSerializer.deserialize(forged)

    def test_tampered_mac_rejected(self):
        token = self._make_token({"count": 1})
        flipped = token[:-1] + ("A" if token[-1] != "A" else "B")
        with pytest.raises(CorruptStateError):
            StateSerializer.deserialize(flipped)

    def test_truncated_token_rejected(self):
        token = self._make_token({"count": 1})
        with pytest.raises(CorruptStateError):
            StateSerializer.deserialize(token[: len(token) // 2])

    def test_garbage_token_rejected(self):
        self._make_token({"count": 1})
        with pytest.raises(CorruptStateError):
            StateSerializer.deserialize("total.garbage.here")

    def test_wrong_version_prefix_rejected(self):
        token = self._make_token({"count": 1})
        with pytest.raises(CorruptStateError):
            StateSerializer.deserialize("cfs2." + token.split(".", 1)[1])

    def test_wrong_key_rejected(self):
        token = self._make_token({"count": 1})
        StateSigner.configure("a-different-key")
        with pytest.raises(CorruptStateError):
            StateSerializer.deserialize(token)


# ---------- Unsigned input while enabled ----------


class TestUnsignedInputRejectedWhenEnabled:
    def test_plain_json_string_rejected(self):
        StateSigner.configure("secret-key")
        with pytest.raises(CorruptStateError):
            StateSerializer.deserialize('{"count": 999}')

    def test_plain_json_string_rejected_via_load_untrusted(self):
        StateSigner.configure("secret-key")
        with pytest.raises(CorruptStateError):
            StateSerializer.load_untrusted('{"count": 999}')

    def test_raw_dict_rejected_via_load_untrusted(self):
        StateSigner.configure("secret-key")
        with pytest.raises(CorruptStateError):
            StateSerializer.load_untrusted({"count": 999})


# ---------- Key rotation ----------


class TestKeyRotation:
    def test_old_token_verifies_after_new_key_prepended(self):
        StateSigner.configure("old-key")
        old_token = StateSerializer.serialize({"count": 7})

        StateSigner.configure(["new-key", "old-key"])
        assert StateSerializer.deserialize(old_token) == {"count": 7}

    def test_new_tokens_signed_with_first_key(self):
        StateSigner.configure(["new-key", "old-key"])
        token = StateSerializer.serialize({"count": 7})

        # A signer holding only the new key must accept it...
        StateSigner.configure("new-key")
        assert StateSerializer.deserialize(token) == {"count": 7}

        # ...and one holding only the old key must reject it.
        StateSigner.configure("old-key")
        with pytest.raises(CorruptStateError):
            StateSerializer.deserialize(token)

    def test_dropping_old_key_invalidates_old_tokens(self):
        StateSigner.configure("old-key")
        old_token = StateSerializer.serialize({"count": 7})
        StateSigner.configure(["new-key"])
        with pytest.raises(CorruptStateError):
            StateSerializer.deserialize(old_token)

    def test_bytes_keys_accepted(self):
        StateSigner.configure(b"binary-key")
        token = StateSerializer.serialize({"ok": True})
        assert StateSerializer.deserialize(token) == {"ok": True}

    def test_empty_key_rejected(self):
        with pytest.raises(ValueError):
            StateSigner.configure("")

    def test_empty_key_list_rejected(self):
        with pytest.raises(ValueError):
            StateSigner.configure([])


# ---------- Disabled (legacy) mode ----------


class TestDisabledMode:
    def test_serialize_returns_plain_json(self):
        result = StateSerializer.serialize({"count": 1})
        assert json.loads(result) == {"count": 1}
        assert not result.startswith("cfs1.")

    def test_deserialize_plain_json(self):
        assert StateSerializer.deserialize('{"count": 1}') == {"count": 1}

    def test_load_untrusted_str_parses_json(self):
        assert StateSerializer.load_untrusted('{"count": 1}') == {"count": 1}

    def test_load_untrusted_dict_passes_through(self):
        state = {"count": 1}
        assert StateSerializer.load_untrusted(state) == state

    def test_load_untrusted_none_and_empty(self):
        assert StateSerializer.load_untrusted(None) is None
        assert StateSerializer.load_untrusted("") is None

    def test_configure_none_disables_even_with_env(self, monkeypatch):
        monkeypatch.setenv("STATE_SIGNING_KEY", "env-key")
        StateSigner.configure(None)
        assert not StateSigner.enabled()
        result = StateSerializer.serialize({"count": 1})
        assert json.loads(result) == {"count": 1}

    def test_unsigned_warning_emitted_once(self, caplog):
        with caplog.at_level(logging.WARNING, logger="component_framework.core.signing"):
            StateSerializer.serialize({"a": 1})
            StateSerializer.serialize({"b": 2})
        unsigned_warnings = [r for r in caplog.records if "unsigned" in r.getMessage().lower()]
        assert len(unsigned_warnings) == 1


# ---------- Environment variable pickup ----------


class TestEnvVarConfiguration:
    def test_env_var_enables_signing(self, monkeypatch):
        monkeypatch.setenv("STATE_SIGNING_KEY", "env-secret")
        assert StateSigner.enabled()
        token = StateSerializer.serialize({"count": 1})
        assert token.startswith("cfs1.")
        assert StateSerializer.deserialize(token) == {"count": 1}

    def test_env_var_comma_separated_rotation(self, monkeypatch):
        monkeypatch.setenv("STATE_SIGNING_KEY", "old-env-key")
        old_token = StateSerializer.serialize({"count": 5})

        monkeypatch.setenv("STATE_SIGNING_KEY", "new-env-key,old-env-key")
        assert StateSerializer.deserialize(old_token) == {"count": 5}

        new_token = StateSerializer.serialize({"count": 6})
        monkeypatch.setenv("STATE_SIGNING_KEY", "new-env-key")
        assert StateSerializer.deserialize(new_token) == {"count": 6}

    def test_configure_takes_precedence_over_env(self, monkeypatch):
        monkeypatch.setenv("STATE_SIGNING_KEY", "env-key")
        StateSigner.configure("explicit-key")
        token = StateSerializer.serialize({"count": 1})
        monkeypatch.delenv("STATE_SIGNING_KEY")
        StateSigner.reset()
        StateSigner.configure("explicit-key")
        assert StateSerializer.deserialize(token) == {"count": 1}


# ---------- Exports ----------


class TestExports:
    def test_core_exports(self):
        import component_framework.core as core

        assert core.CorruptStateError is CorruptStateError
        assert core.StateSigner is StateSigner

    def test_root_exports(self):
        import component_framework

        assert component_framework.CorruptStateError is CorruptStateError
        assert component_framework.StateSigner is StateSigner
        assert "CorruptStateError" in component_framework.__all__
        assert "StateSigner" in component_framework.__all__


# ---------- FastAPI adapter integration ----------


class TestFastAPIIntegration:
    @pytest.fixture
    def client(self, monkeypatch):
        fastapi = pytest.importorskip("fastapi")
        from fastapi.testclient import TestClient

        from component_framework.adapters.fastapi import create_component_routes
        from component_framework.core import Component, Renderer
        from component_framework.core.registry import ComponentRegistry

        class MockRenderer(Renderer):
            def render(self, template_name: str, context: dict) -> str:
                return f"<div>{context.get('state', {})}</div>"

        old_renderer = Component.renderer
        Component.renderer = MockRenderer()

        reg = ComponentRegistry()
        monkeypatch.setattr("component_framework.adapters.fastapi.registry", reg)

        @reg.register("signed_counter")
        class SignedCounter(Component):
            template_name = "counter.html"

            def mount(self):
                super().mount()
                self.state["count"] = 0

            def on_increment(self, amount: int = 1):
                self.state["count"] = self.state.get("count", 0) + amount

        app = fastapi.FastAPI()
        create_component_routes(app)
        yield TestClient(app)
        Component.renderer = old_renderer

    def test_success_path_returns_signed_state(self, client):
        StateSigner.configure("adapter-secret")
        response = client.post("/components/signed_counter", json={})
        assert response.status_code == 200
        assert response.json()["state"].startswith("cfs1.")

    def test_signed_round_trip_through_endpoint(self, client):
        StateSigner.configure("adapter-secret")
        r1 = client.post("/components/signed_counter", json={})
        state_token = r1.json()["state"]

        r2 = client.post(
            "/components/signed_counter",
            json={"event": "increment", "payload": {"amount": 3}, "state": state_token},
        )
        assert r2.status_code == 200
        assert StateSerializer.deserialize(r2.json()["state"]) == {"count": 3}

    def test_tampered_state_returns_400(self, client):
        StateSigner.configure("adapter-secret")
        r1 = client.post("/components/signed_counter", json={})
        token = r1.json()["state"]
        tampered = token[:-2] + ("aa" if not token.endswith("aa") else "bb")

        r2 = client.post(
            "/components/signed_counter",
            json={"event": "increment", "payload": {}, "state": tampered},
        )
        assert r2.status_code == 400

    def test_raw_dict_state_returns_400(self, client):
        StateSigner.configure("adapter-secret")
        r2 = client.post(
            "/components/signed_counter",
            json={"event": "increment", "payload": {}, "state": {"count": 999}},
        )
        assert r2.status_code == 400

    def test_plain_json_string_state_returns_400(self, client):
        StateSigner.configure("adapter-secret")
        r2 = client.post(
            "/components/signed_counter",
            json={"event": "increment", "payload": {}, "state": '{"count": 999}'},
        )
        assert r2.status_code == 400

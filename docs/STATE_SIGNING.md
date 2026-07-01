# State Signing (HMAC)

Component state round-trips through the client on every dispatch: the server
returns a serialized `state` field, and the client echoes it back with the
next event. Without a signature, a client can tamper with any state field
before echoing it back.

State signing closes this gap. When enabled, every outbound state string is
an HMAC-SHA256 signed token, and every inbound state **must** be a valid
token — plain JSON strings and raw JSON objects are rejected with
`CorruptStateError` (HTTP 400 on all adapters).

## Token format

```
cfs1.<base64url(json_payload)>.<base64url(hmac_sha256_mac)>
```

The MAC covers `cfs1.<payload>` — the version prefix is bound into the
signature, so tokens cannot be replayed across future format versions.

## Enabling signing

Signing is configured once per process, at application startup. There are two
equivalent mechanisms:

### 1. Environment variable (no code changes)

```bash
export STATE_SIGNING_KEY="$(openssl rand -hex 32)"
```

Comma-separated values enable key rotation (first key signs, all verify):

```bash
export STATE_SIGNING_KEY="new-key,old-key"
```

### 2. Explicit configuration

```python
from component_framework import StateSigner

StateSigner.configure("your-secret-key")            # single key
StateSigner.configure(["new-key", "old-key"])       # rotation
StateSigner.configure(None)                          # explicitly disable (overrides env)
```

`StateSigner.configure()` takes precedence over the environment variable.

If neither is set, signing is **disabled** and the framework falls back to
legacy plain-JSON state — a one-time warning is logged. Do not run production
deployments unsigned.

## Per-adapter setup

The signer is process-global and lives below the adapter layer, so setup is
the same everywhere: configure it before the app starts serving.

### FastAPI

```python
from fastapi import FastAPI
from component_framework import StateSigner
from component_framework.adapters.fastapi import create_component_routes

StateSigner.configure(os.environ["MY_SECRET"])  # or just set STATE_SIGNING_KEY

app = FastAPI()
create_component_routes(app)
```

### Litestar

```python
from litestar import Litestar
from component_framework import StateSigner
from component_framework.adapters.litestar import component_endpoint

StateSigner.configure(os.environ["MY_SECRET"])

app = Litestar(route_handlers=[component_endpoint])
```

### Flask

```python
from flask import Flask
from component_framework import StateSigner
from component_framework.adapters.flask import register_component_routes

app = Flask(__name__)
StateSigner.configure(app.config["SECRET_KEY"])  # reusing SECRET_KEY is fine
register_component_routes(app)
```

### Django

Configure in `settings.py` (or an `AppConfig.ready()` hook):

```python
# settings.py
from component_framework import StateSigner

StateSigner.configure(SECRET_KEY)  # or a dedicated key
```

## Key rotation procedure

1. **Prepend** the new key: `STATE_SIGNING_KEY="new-key,old-key"` (or
   `StateSigner.configure(["new-key", "old-key"])`). New responses are signed
   with `new-key`; states still in flight (signed with `old-key`) continue to
   verify.
2. **Wait** until in-flight client states have expired — i.e. long enough that
   no open browser tab still holds a state signed with the old key. For most
   apps a deploy cycle or a day is plenty.
3. **Drop** the old key: `STATE_SIGNING_KEY="new-key"`. Old tokens now fail
   verification (clients simply re-mount their components).

## WebSocket pushes

WebSocket traffic goes through the same `StateSerializer` choke point:
inbound `component_event` messages are verified, and both dispatch responses
and server-initiated `push_update()` broadcasts carry signed state.

## Error handling

Tampered, truncated, unsigned, or foreign-key state raises
`component_framework.CorruptStateError` (a `ComponentError` subclass). The
bundled adapters map it to:

| Adapter | Response |
|---------|----------|
| FastAPI | `400` (`HTTPException`) |
| Litestar | `400` (`HTTPException`) |
| Flask | `400` JSON error |
| Django (FBV + CBV) | `400` `JsonResponse` |
| WebSocket | `{"type": "error", ...}` frame |

## What signing does and does not protect

- **Protects:** integrity — the client cannot alter state fields, forge
  state, or splice state across format versions.
- **Does not protect:** confidentiality — the payload is base64-encoded JSON,
  readable by the client. Never put secrets in component state.
- **Does not prevent replay of a stale-but-valid token** for the same
  component. Treat state as untrusted input in handlers and enforce
  authorization server-side. For fields the server owns (roles, IDs,
  pricing), declare them as [locked fields](LOCKED_FIELDS.md) — they never
  round-trip through the client, so replayed blobs cannot roll them back.

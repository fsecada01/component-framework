# Locked Fields (Server-Trusted State)

Component state round-trips through the client on every dispatch. [State
signing](STATE_SIGNING.md) guarantees *integrity* — the client cannot alter a
signed blob — but it does not make state trustworthy:

1. **Unsigned deployments have zero integrity.** If signing is not enabled,
   the client can freely edit any state field before echoing it back.
2. **Even with signing, replay is possible.** A client can capture an *older*
   validly-signed state blob and replay it to roll fields back — e.g. a token
   from before their `is_admin` flag was revoked, a stale `user_id`, or an
   old price.

Locked fields are the defense for values the **server owns**: fields the
client must never influence, in either mode.

## Declaring locked fields

```python
from typing import ClassVar

from component_framework import Component, registry


@registry.register("account_panel")
class AccountPanel(Component):
    template_name = "account_panel.html"
    locked_fields: ClassVar[frozenset[str]] = frozenset({"is_admin", "user_id"})

    def mount(self):
        super().mount()
        self.state["user_id"] = self.params["user"].id
        self.state["is_admin"] = self.params["user"].is_staff
        self.state["tab"] = "profile"

    def before_render(self):
        # Re-derive server-trusted values on EVERY request — hydrated
        # requests do not run mount().
        user = self.params.get("user")
        self.state["is_admin"] = bool(user and user.is_staff)
```

Any iterable of strings works (`frozenset`, `list`, `tuple`); it is
normalized internally. The default is empty — existing components are
unaffected.

## Enforcement semantics

Locked fields are enforced at the core lifecycle choke points, so every
adapter (FastAPI, Flask, Litestar, Django FBV/CBV, WebSocket, SSE streaming)
is covered without adapter changes:

- **Outbound (`dehydrate()`):** locked fields are excluded from the
  serialized state — they never reach the client at all. `self.state` keeps
  them server-side for the rest of the request.
- **Inbound (`hydrate()`):** locked fields present in client-supplied state
  are stripped *before* `self.state` is updated, and a warning is logged
  naming the fields (never the values). Because outbound state never
  contains locked fields, any inbound occurrence is anomalous — crafted
  state, or a replayed blob from before the field was locked.

The inbound dict is sanitized **in place**, so `hydrate()` overrides that
read the raw argument after `super().hydrate(state)` (e.g.
`DjangoModelMixin.hydrate` reading `state["pk"]`) cannot see locked values
either.

## Re-establishing locked values

Since locked values never round-trip, the component must (re)derive them
server-side on every request. Pick whichever fits:

| Pattern | When to use |
|---------|-------------|
| `before_render()` | Value only needed for rendering |
| `hydrate()` override (set after `super().hydrate(state)`) | Value needed by event handlers (handlers run *before* `before_render()`) |
| Server-supplied `params` (adapter/dependency injection) | Value comes from the request context (current user, tenant, …) |
| Look up inside the handler | Value only needed by one handler |

## Interaction with signing

Locked fields work identically in both modes and complement signing:

- **Signing disabled:** locked fields are the only integrity guarantee for
  the fields they cover. Everything else in state remains client-editable —
  enable signing for production.
- **Signing enabled:** signing blocks tampering; locked fields additionally
  block **replay/rollback** of stale-but-validly-signed values for the
  covered fields.

## Caveats

- **Top-level keys only.** `locked_fields` matches top-level state keys.
  Nested values (e.g. one field inside `FormComponent`'s
  `state["form_data"]` dict) cannot be individually locked — keep
  server-trusted values in their own top-level keys, not inside form data.
- **Event payloads are not covered.** Locked fields guard the *state*
  channel. Event payloads (including `FormComponent`'s `submit` payload,
  which writes `form_data` directly) are separate inputs — validate them
  with your Pydantic `schema` and authorization checks in handlers.
- **`ModelFormComponent` / `DjangoModelComponent`:** the bound instance is
  loaded server-side, but `pk` round-trips by design so the mixin can reload
  the instance. Locking `pk` therefore breaks instance reloading — instead,
  authorize access in `get_instance()` (scope the queryset to the current
  user) rather than trusting the client-supplied `pk`.
- **Don't put secrets in state.** Locked or not, state design guidance from
  [State Signing](STATE_SIGNING.md) still applies; locked fields are about
  *trust*, not confidentiality (in fact they never leave the server, which
  also helps confidentiality — but that is a side effect, not a contract).

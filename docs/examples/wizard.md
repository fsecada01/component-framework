# Multi-Step Wizard (FastAPI)

> Runnable example: [`examples/fastapi_wizard_example.py`](../../examples/fastapi_wizard_example.py)

A guided, multi-step form — collect a few fields, validate them, move on,
let the user go back and see what they already entered, then do something
with the accumulated data on the final step. This is the pattern behind
things like onboarding flows, checkout, and (the concrete driver for this
recipe) a resume-tailoring wizard.

---

## Before you build one: read this

**A production-grade wizard needs signed state.** Every component-framework
request round-trips the component's state to the browser and back
(`dispatch(state=...)` → `result["state"]`). Today that round-trip is
**unsigned** — nothing stops a client from editing the serialized state blob
before posting it back. For a single counter that's harmless. For a wizard
that accumulates several steps of validated data, a tampered state blob
could let a client skip validation on an earlier step, or submit the final
step with fabricated `collected` data for an earlier one.

Signed state is tracked as **Epic A / A1** and does not exist yet as of this
writing (no `CorruptStateError`, no `sign_state`, nothing in
`core/component.py`'s `StateSerializer`). **A4** (CSRF coverage for the
FastAPI adapter) is also outstanding — the FastAPI adapter has no CSRF
handling at all right now, unlike the Django adapter.

This recipe and its example are written against the **current, unsigned**
state model, so you can build a wizard today. Two things to do once A1/A4
land:

- Swap the plain `state=...` round-trip for whatever signed-state API A1
  introduces — no change to the component's own logic should be needed.
- Add CSRF protection at the app level for the wizard's POST route (a
  double-submit-cookie middleware, or whatever your app already uses for
  other POST endpoints) until A4 ships a first-class mechanism.

Until then: **don't put anything in a wizard's accumulated state that you
wouldn't be comfortable with a malicious client tampering with.** If the
final step's handler is about to write to your database, re-validate the
data you actually need server-side rather than trusting `collected`
blindly (e.g. re-check foreign keys exist, re-check ownership).

---

## Why not `CompositeComponent` per step?

If you've read the framework's docs/README, you may expect a
`CompositeComponent` host with one child `FormComponent` per step, wired
via slots. **That primitive doesn't exist in the codebase today** — only
`Component.fill_slot()` / `render_slots()` and the `compose()` helper in
`core/composition.py`, which compose components for **rendering** (a parent
template with pre-rendered child HTML dropped into named slots).

That's a fundamentally different problem than a wizard's needs. Each POST to
`/components/{name}` dispatches **exactly one** registered component — hydrate
→ handle event → render → dehydrate — for that one component only. There's
no framework machinery that would hydrate a parent *and* an independently
addressable per-step child component in the same request and keep both
in sync across steps. Modeling a wizard as a parent + slotted children
would mean inventing your own protocol for shuttling child state through
the parent's state anyway — at which point you've just built the pattern
below with extra ceremony.

**The pattern that actually works:** one component owns the whole wizard.
It tracks which step is active and the data collected so far, and swaps
which schema it validates against based on the active step.

---

## The Component

```python
# resume_wizard.py
from typing import ClassVar

from pydantic import BaseModel, EmailStr, Field

from component_framework.core import FormComponent, registry


class ContactStepSchema(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr


class TargetRoleStepSchema(BaseModel):
    job_title: str = Field(min_length=2, max_length=100)
    company: str = Field(min_length=2, max_length=100)


# The final "review" step has no fields to validate, so no schema.
STEPS: list[dict] = [
    {"key": "contact", "title": "Contact Info", "schema": ContactStepSchema},
    {"key": "target_role", "title": "Target Role", "schema": TargetRoleStepSchema},
    {"key": "review", "title": "Review & Generate", "schema": None},
]


@registry.register("resume_wizard")
class ResumeWizard(FormComponent):
    steps: ClassVar[list[dict]] = STEPS
    template_name = "Wizard"

    def mount(self):
        super().mount()
        self.state.setdefault("step_index", 0)
        self.state.setdefault("collected", {})
        self._load_current_step_form_data()

    def _current_step(self) -> dict:
        return self.steps[self.state["step_index"]]

    def _load_current_step_form_data(self):
        """Pre-fill from previously-entered data when navigating back."""
        step = self._current_step()
        self.state["form_data"] = self.state["collected"].get(step["key"], {})
        self.field_errors = {}

    @property
    def schema(self):
        """FormComponent.validate() reads this — point it at the active step."""
        return self._current_step().get("schema")

    def on_advance(self, form_data: dict):
        step = self._current_step()
        self.state["form_data"] = form_data

        if step.get("schema") and not self.validate(form_data):
            return  # field_errors populated by validate(); stay on this step

        if step.get("schema"):
            self.state["collected"][step["key"]] = self.validated_data

        if self.state["step_index"] < len(self.steps) - 1:
            self.state["step_index"] += 1
            self._load_current_step_form_data()

    def on_back(self):
        if self.state["step_index"] > 0:
            self.state["step_index"] -= 1
            self._load_current_step_form_data()

    def on_submit(self):
        """
        Final step. This is where an app persists the wizard's result —
        the framework does not do this for you. For example:

            ResumeDraft.objects.create(**self.state["collected"]["contact"], ...)

        Re-validate anything security-sensitive here rather than trusting
        ``collected`` outright — see the state-signing caveat above.
        """
        self.state["completed"] = True

    def get_context(self) -> dict:
        context = super().get_context()
        context.update({
            "step_index": self.state["step_index"],
            "step_key": self._current_step()["key"],
            "step_title": self._current_step()["title"],
            "step_titles": [s["title"] for s in self.steps],
            "is_last_step": self.state["step_index"] == len(self.steps) - 1,
            "collected": self.state.get("collected", {}),
            "completed": self.state.get("completed", False),
        })
        return context
```

Three things make this work:

1. **`schema` becomes a property, not a fixed `ClassVar`.** `FormComponent.validate()`
   reads `self.schema` — overriding it as a property lets each step supply its
   own Pydantic model without needing per-step component subclasses.
2. **`on_advance` validates and *then* decides whether to move.** A failed
   validation leaves `step_index` untouched and populates `field_errors`
   exactly like a single-page `FormComponent` would — the difference is just
   that we route through `validate()` manually instead of going through
   `handle_event`'s built-in `"submit"` branch.
3. **The last step reuses `"submit"`, not `"advance"`.** Since the review
   step has `schema: None`, `FormComponent.handle_event`'s existing
   `"submit"` handling (validate → call `on_submit`) works unchanged — no
   special-casing needed for the terminal step.

## The Template

The template switches which fields it renders based on `step_key`, and
posts each field's live value explicitly via `hx-vals='js:{...}'` (rather
than relying on `hx-include`, which doesn't nest into the component
endpoint's `payload.form_data` shape). See
[`templates/components/Wizard.jinja`](../../templates/components/Wizard.jinja)
for the full template — the "Next" button on the contact step looks like:

```html
<button
  type="button"
  hx-post="/components/resume_wizard"
  hx-vals='js:{"event": "advance", "payload": {"form_data": {"name": document.getElementById("wiz-name").value, "email": document.getElementById("wiz-email").value}}, "state": {{ state | tojson }}, "params": {"component_id": "{{ component_id }}"}}'
  hx-target="#{{ component_id }}"
  hx-swap="outerHTML"
>Next</button>
```

"Back" posts an `"back"` event with an empty payload; the final step's
"Generate" button posts `"submit"`.

## What happens to state when you navigate

- **In-flight wizard data lives entirely in the client-held state blob**
  (unsigned today, signed once A1 lands) — not on the server, not in a
  database. If the
  user closes the tab mid-wizard, everything they entered is gone unless
  your app persists it somewhere (e.g. autosaving `collected` after each
  step).
- **Going back doesn't discard anything.** `on_back` only moves
  `step_index`; `collected` is untouched, so `_load_current_step_form_data`
  re-populates the earlier step's fields from what's already stored.
- **The framework never writes anything server-side.** `on_submit` is where
  *your app* takes `self.state["collected"]` and does something durable
  with it (save a model, kick off a background job, etc.) — component-framework's
  job ends at handing you validated, accumulated data.

## Running it

```bash
uv run python examples/fastapi_wizard_example.py
```

Open `http://localhost:8000` — fill in contact info and target role (try an
invalid email to see per-field validation), navigate back and confirm your
answers are still there, then generate on the review step.

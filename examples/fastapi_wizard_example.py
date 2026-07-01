"""FastAPI example: a multi-step wizard built from a single stateful component.

Scenario: a 3-step "resume tailoring" wizard (contact info -> target role ->
review/generate) — the reference pattern for Resume-Generator's wizard flow.

NOTE ON STATE SECURITY: this example round-trips wizard state to the client
unsigned, as component-framework does not yet ship signed state (tracked as
Epic A / A1). Do not use this pattern for wizards that collect sensitive data
until A1 lands — see docs/examples/wizard.md for details.
"""

import sys
from pathlib import Path
from typing import ClassVar

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from jinjax import Catalog
from pydantic import BaseModel, EmailStr, Field

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from component_framework.adapters.fastapi import create_component_routes
from component_framework.adapters.jinjax_renderer import JinjaxRenderer
from component_framework.core import Component, FormComponent, registry

# Initialize FastAPI
app = FastAPI(title="Component Framework - Wizard Demo")

# Setup Jinjax
templates_dir = Path(__file__).parent.parent / "templates" / "components"
catalog = Catalog()
catalog.add_folder(templates_dir)
catalog.jinja_env.autoescape = True

# Configure renderer globally
renderer = JinjaxRenderer(catalog)
Component.renderer = renderer


# ---------- Per-step schemas ----------


class ContactStepSchema(BaseModel):
    """Step 1: who the resume is for."""

    name: str = Field(min_length=2, max_length=100)
    email: EmailStr


class TargetRoleStepSchema(BaseModel):
    """Step 2: what role the resume should be tailored for."""

    job_title: str = Field(min_length=2, max_length=100)
    company: str = Field(min_length=2, max_length=100)


# The final "review" step has no input fields to validate — it just confirms
# the accumulated data and triggers generation, so it has no schema.

STEPS: list[dict] = [
    {"key": "contact", "title": "Contact Info", "schema": ContactStepSchema},
    {"key": "target_role", "title": "Target Role", "schema": TargetRoleStepSchema},
    {"key": "review", "title": "Review & Generate", "schema": None},
]


# ---------- Component ----------


@registry.register("resume_wizard")
class ResumeWizard(FormComponent):
    """
    Multi-step wizard implemented as a single component that owns
    ``step_index`` and swaps which step's fields/schema are active.

    There is no ``CompositeComponent``-per-step primitive in the framework
    today — each POST to /components/{name} dispatches exactly one
    registered component, so a wizard's cross-step state (which step is
    active, and what was entered on earlier steps) has to live on one
    component rather than being split across independently-dispatched
    child components. See docs/examples/wizard.md for the full writeup.
    """

    steps: ClassVar[list[dict]] = STEPS
    template_name = "Wizard"

    def mount(self):
        super().mount()
        self.state.setdefault("step_index", 0)
        self.state.setdefault("collected", {})
        self._load_current_step_form_data()

    # ---------- Step helpers ----------

    def _current_step(self) -> dict:
        return self.steps[self.state["step_index"]]

    def _load_current_step_form_data(self):
        """Pre-fill form_data from previously-entered data for this step."""
        step = self._current_step()
        self.state["form_data"] = self.state["collected"].get(step["key"], {})
        self.field_errors = {}

    @property
    def schema(self):
        """Validate against the *active* step's schema, not a fixed one."""
        return self._current_step().get("schema")

    # ---------- Navigation ----------

    def on_advance(self, form_data: dict):
        """Validate the current step and move to the next one."""
        step = self._current_step()
        self.state["form_data"] = form_data

        if step.get("schema") and not self.validate(form_data):
            # field_errors is populated by validate(); stay on this step.
            return

        if step.get("schema"):
            self.state["collected"][step["key"]] = self.validated_data

        if self.state["step_index"] < len(self.steps) - 1:
            self.state["step_index"] += 1
            self._load_current_step_form_data()

    def on_back(self):
        """Move to the previous step without validating the current one."""
        if self.state["step_index"] > 0:
            self.state["step_index"] -= 1
            self._load_current_step_form_data()

    def on_submit(self):
        """
        Final step: hand the accumulated wizard data to the application.

        The framework does not persist this anywhere — that's an app-level
        concern. A real app would write ``self.state["collected"]`` to its
        own models here (e.g. create a ResumeDraft row).
        """
        self.state["completed"] = True

    # ---------- Context ----------

    def get_context(self) -> dict:
        context = super().get_context()
        context.update(
            {
                "step_index": self.state["step_index"],
                "step_key": self._current_step()["key"],
                "step_title": self._current_step()["title"],
                "step_titles": [s["title"] for s in self.steps],
                "is_last_step": self.state["step_index"] == len(self.steps) - 1,
                "collected": self.state.get("collected", {}),
                "completed": self.state.get("completed", False),
            }
        )
        return context


# Add component routes
create_component_routes(app)


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve demo page with initial wizard render."""
    wizard = ResumeWizard()
    result = wizard.dispatch()

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Wizard Component Demo</title>
        <script src="https://unpkg.com/htmx.org@1.9.10"></script>
        <style>
            body {{
                font-family: system-ui, -apple-system, sans-serif;
                max-width: 600px;
                margin: 50px auto;
                padding: 20px;
                color: #333;
            }}
            h1 {{ text-align: center; }}
            .info {{
                background: #e3f2fd;
                padding: 15px;
                border-radius: 8px;
                margin: 20px 0;
            }}
        </style>
    </head>
    <body>
        <h1>Resume Wizard Demo</h1>

        <div class="info">
            <p>A 3-step wizard built from <strong>one stateful component</strong>
            that tracks <code>step_index</code> and per-step validated data.
            Unsigned state round-trip — see docs/examples/wizard.md.</p>
        </div>

        {result["html"]}
    </body>
    </html>
    """


if __name__ == "__main__":
    import uvicorn

    print("Starting Wizard Component Demo")
    print("Open http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)

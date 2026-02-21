"""FastAPI example with a form component demonstrating Pydantic validation."""

import sys
from pathlib import Path

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
app = FastAPI(title="Component Framework - Form Demo")

# Setup Jinjax
templates_dir = Path(__file__).parent.parent / "templates" / "components"
catalog = Catalog()
catalog.add_folder(templates_dir)
catalog.jinja_env.autoescape = True

# Configure renderer globally
renderer = JinjaxRenderer(catalog)
Component.renderer = renderer


# ---------- Schema ----------


class ContactSchema(BaseModel):
    """Validation schema for the contact form."""

    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    message: str = Field(min_length=10, max_length=500)


# ---------- Component ----------


@registry.register("contact_form")
class ContactForm(FormComponent):
    """Contact form with server-side validation."""

    schema = ContactSchema
    template_name = "ContactForm"

    def on_submit(self):
        """Handle successful submission."""
        self.state["success_message"] = (
            f"Thanks {self.validated_data['name']}! We received your message."
        )


# Add component routes
create_component_routes(app)


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve demo page with initial form render."""
    form = ContactForm()
    result = form.dispatch()

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Form Component Demo</title>
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
        <h1>Form Component Demo</h1>

        <div class="info">
            <p>This form uses <strong>Pydantic validation</strong> on the server.
            Submit with invalid data to see field-level errors.</p>
        </div>

        {result["html"]}
    </body>
    </html>
    """


if __name__ == "__main__":
    import uvicorn

    print("Starting Form Component Demo")
    print("Open http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)

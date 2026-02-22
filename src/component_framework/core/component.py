"""Core component base class with lifecycle management."""

import json
import logging
from typing import TYPE_CHECKING, Any, ClassVar
from uuid import uuid4

if TYPE_CHECKING:
    from .permissions import BasePermission

logger = logging.getLogger(__name__)


class ComponentError(Exception):
    """Base exception for component errors."""

    pass


class EventNotFoundError(ComponentError):
    """Raised when an event handler is not found."""

    pass


class Component:
    """
    Base component class with lifecycle management.

    Lifecycle:
        1. __init__(**params)
        2. mount() OR hydrate(state)
        3. handle_event(event, payload)
        4. before_render()
        5. render()
        6. dehydrate()
    """

    template_name: str | None = None
    renderer = None
    permission_classes: ClassVar[list[type["BasePermission"]]] = []

    def __init__(self, **params):
        self.params = params
        self.state: dict[str, Any] = {}
        self.errors: dict[str, str] = {}
        self.id = params.get("component_id") or self._generate_id()
        self._mounted = False

    # ---------- Lifecycle ----------

    def _generate_id(self) -> str:
        """Generate unique component ID."""
        return f"component-{uuid4().hex[:8]}"

    def mount(self):
        """Initialize component on first load. Override in subclasses."""
        self._mounted = True

    def hydrate(self, state: dict):
        """Restore component from serialized state."""
        self.state.update(state)
        self._mounted = True

    def dehydrate(self) -> dict:
        """Serialize component state for persistence."""
        return self.state.copy()

    def before_render(self):
        """Called before rendering. Use for derived state computation."""
        pass

    # ---------- Events ----------

    def handle_event(self, event: str, payload: dict):
        """
        Route event to handler method.

        Args:
            event: Event name (e.g., "increment")
            payload: Event data

        Raises:
            EventNotFoundError: If handler not found
            ComponentError: If handler raises exception
        """
        handler = getattr(self, f"on_{event}", None)

        if not handler:
            raise EventNotFoundError(f"No handler for event: {event}")

        try:
            handler(**payload)
        except TypeError as e:
            raise ComponentError(f"Invalid payload for {event}: {e}") from e
        except Exception as e:
            logger.exception(f"Error handling {event} in {self.__class__.__name__}")
            raise ComponentError(f"Error handling {event}") from e

    # ---------- Rendering ----------

    def get_context(self) -> dict:
        """
        Build template context. Does not expose full component.

        Override to add custom context variables.
        """
        return {
            "state": self.state,
            "errors": self.errors,
            "component_id": self.id,
        }

    def render(self) -> str:
        """Render component to HTML."""
        if not self.renderer:
            raise ComponentError("No renderer configured")

        if not self.template_name:
            raise ComponentError("No template_name specified")

        self.before_render()

        return self.renderer.render(
            self.template_name,
            self.get_context(),
        )

    # ---------- Dispatch ----------

    def dispatch(
        self,
        event: str | None = None,
        payload: dict | None = None,
        state: dict | None = None,
    ) -> dict:
        """
        Main entry point for component execution.

        Args:
            event: Event name to handle
            payload: Event data
            state: Serialized state to restore

        Returns:
            Dict with 'html' and 'state' keys
        """
        try:
            # Lifecycle: mount or hydrate
            if state:
                self.hydrate(state)
            else:
                self.mount()

            # Handle event if provided
            if event:
                self.handle_event(event, payload or {})

            # Render
            html = self.render()

            return {
                "html": html,
                "state": self.dehydrate(),
                "component_id": self.id,
            }

        except Exception:
            logger.exception(f"Error in {self.__class__.__name__}.dispatch()")
            raise


class StateSerializer:
    """Handles safe serialization/deserialization of component state."""

    @staticmethod
    def serialize(state: dict) -> str:
        """Serialize state to JSON string."""
        return json.dumps(state, default=str)

    @staticmethod
    def deserialize(data: str) -> dict:
        """Deserialize state from JSON string."""
        if not data:
            return {}
        return json.loads(data)

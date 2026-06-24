"""Core component base class with lifecycle management."""

import inspect
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

    Slots:
        Components can declare named slots via the ``slots`` class variable.
        Child components are assigned to slots with ``fill_slot()`` and their
        rendered HTML is available in the template context under ``slots``.
    """

    template_name: str | None = None
    renderer = None
    permission_classes: ClassVar[list[type["BasePermission"]]] = []
    slots: ClassVar[list[str]] = []
    """Slot names this component accepts. Empty list means *any* slot name is accepted."""

    def __init__(self, **params):
        self.params = params
        self.state: dict[str, Any] = {}
        self.errors: dict[str, str] = {}
        self.id = params.get("component_id") or self._generate_id()
        self._mounted = False
        self._slot_components: dict[str, Component] = {}

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

    # ---------- Slots / Composition ----------

    def fill_slot(self, slot_name: str, component: "Component") -> None:
        """
        Assign a child component to a named slot.

        If the component declares specific ``slots``, *slot_name* must be one of
        them.  If ``slots`` is empty (the default), any name is accepted
        (permissive mode).

        Args:
            slot_name: Target slot identifier.
            component: Child component instance to render in the slot.

        Raises:
            ComponentError: If *slot_name* is not in the declared ``slots`` list.
        """
        if self.slots and slot_name not in self.slots:
            raise ComponentError(f"Unknown slot '{slot_name}'. Available: {self.slots}")
        self._slot_components[slot_name] = component

    def render_slots(self) -> dict[str, str]:
        """
        Render all filled slot components.

        Returns:
            Dict mapping slot names to their rendered HTML strings.
        """
        rendered: dict[str, str] = {}
        for name, child in self._slot_components.items():
            rendered[name] = child.render()
        return rendered

    # ---------- Optimistic UI ----------

    def get_optimistic_patch(self, event: str, payload: dict) -> dict | None:
        """
        Return the anticipated partial state dict for the given event and payload.

        When non-None, this patch is attached to the dispatch response under the
        ``optimistic`` key. Because it is delivered *alongside* the authoritative render,
        it does not by itself produce instant feedback — the full render overwrites the
        DOM in the same response cycle. It is exposed for inspection (e.g. the client's
        ``onUpdate`` callback) and for forward streaming support.

        For genuine instant feedback, use the client-side declarative prediction in
        ``component-client.js``: add ``data-optimistic='{...}'`` or
        ``data-optimistic-toggle="field"`` to the trigger element. The client applies that
        patch synchronously at click time and reconciles it with this server render.

        Override in subclasses to advertise the predicted state for specific events. Return
        None (the default) to omit the ``optimistic`` key for a given event.

        Args:
            event: The event name being dispatched (e.g., "increment").
            payload: The event payload dict.

        Returns:
            A partial state dict describing the anticipated state, or None to skip.

        Example::

            def get_optimistic_patch(self, event: str, payload: dict) -> dict | None:
                if event == "increment":
                    return {"count": self.state.get("count", 0) + payload.get("amount", 1)}
                return None
        """
        return None

    # ---------- Events ----------

    def handle_event(self, event: str, payload: dict):
        """
        Route event to a **synchronous** handler method.

        For async handlers (``async def on_*``), use :meth:`async_handle_event`
        instead.  Calling this method with an async handler will raise
        :class:`ComponentError`.

        Args:
            event: Event name (e.g., "increment")
            payload: Event data

        Raises:
            EventNotFoundError: If handler not found
            ComponentError: If handler raises exception or is async
        """
        handler = getattr(self, f"on_{event}", None)

        if not handler:
            raise EventNotFoundError(f"No handler for event: {event}")

        if inspect.iscoroutinefunction(handler):
            raise ComponentError(
                f"Handler 'on_{event}' is async — use async_dispatch() or "
                "async_handle_event() instead of the sync variants."
            )

        try:
            handler(**payload)
        except TypeError as e:
            raise ComponentError(f"Invalid payload for {event}: {e}") from e
        except Exception as e:
            logger.exception(f"Error handling {event} in {self.__class__.__name__}")
            raise ComponentError(f"Error handling {event}") from e

    async def async_handle_event(self, event: str, payload: dict):
        """
        Route event to handler, awaiting if the handler is async.

        Works with both ``def on_*`` and ``async def on_*`` handlers.

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
            result = handler(**payload)
            if inspect.isawaitable(result):
                await result
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
        The returned dict always includes a ``slots`` key containing the
        rendered HTML of any filled child components.
        """
        return {
            "state": self.state,
            "errors": self.errors,
            "component_id": self.id,
            "slots": self.render_slots(),
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
        Synchronous entry point for component execution.

        For components with ``async def on_*`` handlers, use
        :meth:`async_dispatch` instead.

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
                "slots": self.render_slots(),
            }

        except Exception:
            logger.exception(f"Error in {self.__class__.__name__}.dispatch()")
            raise

    async def async_dispatch(
        self,
        event: str | None = None,
        payload: dict | None = None,
        state: dict | None = None,
    ) -> dict:
        """
        Async entry point for component execution.

        Works with both sync and async event handlers.  Use this from async
        adapters (FastAPI, Litestar, WebSocket) to support ``async def on_*``
        handlers.

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
                await self.async_handle_event(event, payload or {})

            # Render
            html = self.render()

            return {
                "html": html,
                "state": self.dehydrate(),
                "component_id": self.id,
                "slots": self.render_slots(),
            }

        except Exception:
            logger.exception(f"Error in {self.__class__.__name__}.async_dispatch()")
            raise


class StateSerializer:
    """Handles safe serialization/deserialization of component state.

    Class attributes:
        warn_bytes: Emit a warning when serialised state exceeds this size
            (default 64 KB).  Set to ``0`` to disable warnings.
        max_bytes: Raise :class:`ComponentError` when serialised state exceeds
            this size (default 512 KB).  Set to ``0`` to disable the hard limit.
    """

    warn_bytes: int = 64 * 1024  # 64 KB
    max_bytes: int = 512 * 1024  # 512 KB

    @staticmethod
    def serialize(state: dict) -> str:
        """Serialize state to JSON string.

        Emits a warning if the result exceeds :attr:`warn_bytes` and raises
        :class:`ComponentError` if it exceeds :attr:`max_bytes`.
        """
        serialized = json.dumps(state, default=str)
        size = len(serialized)

        if StateSerializer.max_bytes and size > StateSerializer.max_bytes:
            raise ComponentError(
                f"Component state is {size:,} bytes "
                f"(hard limit: {StateSerializer.max_bytes:,}). "
                "Move large data out of state — store IDs/keys instead of "
                "full objects, or use server-side caching."
            )

        if StateSerializer.warn_bytes and size > StateSerializer.warn_bytes:
            logger.warning(
                "Component state is %s bytes (threshold: %s). "
                "Consider moving large data out of state.",
                f"{size:,}",
                f"{StateSerializer.warn_bytes:,}",
            )

        return serialized

    @staticmethod
    def deserialize(data: str) -> dict:
        """Deserialize state from JSON string."""
        if not data:
            return {}
        return json.loads(data)

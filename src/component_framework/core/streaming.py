"""Streaming component support for SSE-based progressive rendering."""

import inspect
import json
import logging
from collections.abc import AsyncGenerator

from .component import Component, ComponentError, EventNotFoundError

logger = logging.getLogger(__name__)


class StreamingComponent(Component):
    """
    Component subclass that supports streaming intermediate renders via SSE.

    Event handlers written as async generators will yield intermediate frames.
    Each ``yield`` triggers a render and emits the current state as an SSE frame.

    Example::

        @registry.register("rag_query")
        class RagQueryComponent(StreamingComponent):
            template_name = "rag_query.html"

            async def on_analyze(self, query: str):
                async for step in rag_service.stream(query):
                    self.state["step"] = step
                    yield  # emit intermediate render
                self.state["done"] = True

    Non-generator handlers (sync or async) are also supported and produce a
    single frame, making the streaming endpoint backward-compatible.
    """

    async def async_stream_dispatch(
        self,
        event: str | None = None,
        payload: dict | None = None,
        state: dict | None = None,
    ) -> AsyncGenerator[dict, None]:
        """
        Async generator entry point for streaming component execution.

        Yields one dict per intermediate render, plus a final frame with
        ``stream_done=True``.  Each frame has the same shape as ``dispatch()``
        output, with an added ``stream_done`` key.

        Args:
            event: Event name to handle.
            payload: Event data.
            state: Serialized state to restore.

        Yields:
            Dict with ``html``, ``state``, ``component_id``, ``slots``, and
            ``stream_done`` keys.
        """
        try:
            # Lifecycle: mount or hydrate
            if state:
                self.hydrate(state)
            else:
                self.mount()

            if not event:
                # No event — just render once
                yield self._render_frame(stream_done=True)
                return

            handler = getattr(self, f"on_{event}", None)
            if not handler:
                raise EventNotFoundError(f"No handler for event: {event}")

            if inspect.isasyncgenfunction(handler):
                # Async generator handler — yield intermediate frames
                try:
                    async for _ in handler(**(payload or {})):
                        yield self._render_frame(stream_done=False)
                except TypeError as e:
                    raise ComponentError(f"Invalid payload for {event}: {e}") from e
                except ComponentError:
                    raise
                except Exception as e:
                    logger.exception(f"Error handling {event} in {self.__class__.__name__}")
                    raise ComponentError(f"Error handling {event}") from e

                # Final frame after generator exhaustion
                yield self._render_frame(stream_done=True)

            else:
                # Non-generator handler (sync or async) — single frame
                try:
                    result = handler(**(payload or {}))
                    if inspect.isawaitable(result):
                        await result
                except TypeError as e:
                    raise ComponentError(f"Invalid payload for {event}: {e}") from e
                except ComponentError:
                    raise
                except Exception as e:
                    logger.exception(f"Error handling {event} in {self.__class__.__name__}")
                    raise ComponentError(f"Error handling {event}") from e

                yield self._render_frame(stream_done=True)

        except Exception:
            logger.exception(f"Error in {self.__class__.__name__}.async_stream_dispatch()")
            raise

    def _render_frame(self, *, stream_done: bool) -> dict:
        """Render the component and return a frame dict."""
        self.before_render()
        html = self.render()
        return {
            "html": html,
            "state": self.dehydrate(),
            "component_id": self.id,
            "slots": self.render_slots(),
            "stream_done": stream_done,
        }


def format_sse_frame(frame: dict) -> str:
    """Format a frame dict as an SSE ``data:`` line.

    Args:
        frame: The frame dict from ``async_stream_dispatch``.

    Returns:
        A string ending with two newlines (SSE message terminator).
    """
    return f"data: {json.dumps(frame, default=str)}\n\n"

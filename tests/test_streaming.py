"""Tests for StreamingComponent and SSE streaming dispatch."""

import json

import pytest

from component_framework.core.component import ComponentError, EventNotFoundError
from component_framework.core.renderer import Renderer
from component_framework.core.streaming import StreamingComponent, format_sse_frame


class MockRenderer(Renderer):
    def render(self, template_name: str, context: dict) -> str:
        return f"<div>{template_name}: {context.get('state', {})}</div>"


@pytest.fixture(autouse=True)
def _setup_renderer():
    old = StreamingComponent.renderer
    StreamingComponent.renderer = MockRenderer()
    yield
    StreamingComponent.renderer = old


# ---------- Test components ----------


class StepStreamComponent(StreamingComponent):
    """Component with an async generator handler that yields 3 steps."""

    template_name = "stream.html"

    def mount(self):
        super().mount()
        self.state["step"] = 0
        self.state["done"] = False

    async def on_process(self, steps: int = 3):
        for i in range(1, steps + 1):
            self.state["step"] = i
            yield
        self.state["done"] = True


class AsyncNonGenComponent(StreamingComponent):
    """Component with a regular async handler (no yield)."""

    template_name = "nogen.html"

    def mount(self):
        super().mount()
        self.state["value"] = 0

    async def on_update(self, value: int = 0):
        self.state["value"] = value


class SyncHandlerStreamComponent(StreamingComponent):
    """Component with a sync handler used via streaming endpoint."""

    template_name = "sync.html"

    def mount(self):
        super().mount()
        self.state["value"] = 0

    def on_update(self, value: int = 0):
        self.state["value"] = value


class FailingStreamComponent(StreamingComponent):
    """Component with a generator that raises mid-stream."""

    template_name = "fail.html"

    def mount(self):
        super().mount()
        self.state["step"] = 0

    async def on_process(self):
        self.state["step"] = 1
        yield
        raise ValueError("intentional mid-stream error")


# ---------- async_stream_dispatch ----------


class TestAsyncStreamDispatch:
    @pytest.mark.asyncio
    async def test_yields_intermediate_and_final_frames(self):
        comp = StepStreamComponent()
        gen = comp.async_stream_dispatch(event="process", payload={"steps": 3})
        frames = [f async for f in gen]
        assert len(frames) == 4  # 3 intermediate + 1 final
        for f in frames[:-1]:
            assert f["stream_done"] is False
        assert frames[-1]["stream_done"] is True
        assert frames[-1]["state"]["done"] is True

    @pytest.mark.asyncio
    async def test_intermediate_states_are_progressive(self):
        comp = StepStreamComponent()
        gen = comp.async_stream_dispatch(event="process", payload={"steps": 3})
        frames = [f async for f in gen]
        steps = [f["state"]["step"] for f in frames]
        assert steps == [1, 2, 3, 3]  # last frame has same step as 3rd yield

    @pytest.mark.asyncio
    async def test_each_frame_has_html(self):
        comp = StepStreamComponent()
        frames = [f async for f in comp.async_stream_dispatch(event="process")]
        for f in frames:
            assert "html" in f
            assert "stream.html" in f["html"]

    @pytest.mark.asyncio
    async def test_non_generator_handler_single_frame(self):
        comp = AsyncNonGenComponent()
        gen = comp.async_stream_dispatch(event="update", payload={"value": 42})
        frames = [f async for f in gen]
        assert len(frames) == 1
        assert frames[0]["stream_done"] is True
        assert frames[0]["state"]["value"] == 42

    @pytest.mark.asyncio
    async def test_sync_handler_single_frame(self):
        comp = SyncHandlerStreamComponent()
        frames = [f async for f in comp.async_stream_dispatch(event="update", payload={"value": 7})]
        assert len(frames) == 1
        assert frames[0]["stream_done"] is True
        assert frames[0]["state"]["value"] == 7

    @pytest.mark.asyncio
    async def test_no_event_single_frame(self):
        comp = StepStreamComponent()
        frames = [f async for f in comp.async_stream_dispatch()]
        assert len(frames) == 1
        assert frames[0]["stream_done"] is True

    @pytest.mark.asyncio
    async def test_hydrate_path(self):
        comp = StepStreamComponent()
        frames = [
            f
            async for f in comp.async_stream_dispatch(
                event="process", payload={"steps": 1}, state={"step": 10, "done": False}
            )
        ]
        # Hydrated with step=10, then handler sets step=1
        assert frames[0]["state"]["step"] == 1

    @pytest.mark.asyncio
    async def test_missing_handler_raises(self):
        comp = StepStreamComponent()
        with pytest.raises(EventNotFoundError):
            async for _ in comp.async_stream_dispatch(event="nonexistent"):
                pass

    @pytest.mark.asyncio
    async def test_handler_error_propagates(self):
        comp = FailingStreamComponent()
        frames = []
        with pytest.raises(ComponentError, match="Error handling process"):
            async for f in comp.async_stream_dispatch(event="process"):
                frames.append(f)
        # Should have yielded 1 intermediate frame before the error
        assert len(frames) == 1
        assert frames[0]["state"]["step"] == 1

    @pytest.mark.asyncio
    async def test_frame_contains_component_id(self):
        comp = StepStreamComponent(component_id="stream-123")
        gen = comp.async_stream_dispatch(event="process", payload={"steps": 1})
        frames = [f async for f in gen]
        for f in frames:
            assert f["component_id"] == "stream-123"


# ---------- format_sse_frame ----------


class TestFormatSseFrame:
    def test_basic_format(self):
        frame = {"html": "<div>test</div>", "state": {"k": "v"}, "stream_done": False}
        result = format_sse_frame(frame)
        assert result.startswith("data: ")
        assert result.endswith("\n\n")
        parsed = json.loads(result[len("data: ") :])
        assert parsed["html"] == "<div>test</div>"

    def test_roundtrip_json(self):
        frame = {
            "html": "<p>hi</p>",
            "state": {"count": 1},
            "component_id": "x",
            "stream_done": True,
        }
        result = format_sse_frame(frame)
        parsed = json.loads(result.removeprefix("data: ").strip())
        assert parsed == frame

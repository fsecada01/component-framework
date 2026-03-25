"""Core framework components."""

from .component import Component, ComponentError, EventNotFoundError, StateSerializer
from .composition import SlotRenderer, compose
from .form import FormComponent, ModelFormComponent
from .permissions import (
    AllowAny,
    BasePermission,
    DjangoModelPermission,
    IsAuthenticated,
    IsStaff,
    IsSuperuser,
)
from .registry import ComponentRegistry, registry
from .renderer import Renderer
from .state import InMemoryStateStore, StateStore
from .streaming import StreamingComponent, format_sse_frame
from .websocket import ComponentWebSocketManager, WebSocketConnection, ws_manager

__all__ = [
    "Component",
    "ComponentError",
    "EventNotFoundError",
    "StateSerializer",
    "compose",
    "SlotRenderer",
    "FormComponent",
    "ModelFormComponent",
    "AllowAny",
    "BasePermission",
    "DjangoModelPermission",
    "IsAuthenticated",
    "IsStaff",
    "IsSuperuser",
    "ComponentRegistry",
    "registry",
    "Renderer",
    "StateStore",
    "InMemoryStateStore",
    "StreamingComponent",
    "format_sse_frame",
    "ComponentWebSocketManager",
    "WebSocketConnection",
    "ws_manager",
]

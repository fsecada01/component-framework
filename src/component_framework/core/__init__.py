"""Core framework components."""

from .component import Component, ComponentError, EventNotFoundError, StateSerializer
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
from .websocket import ComponentWebSocketManager, WebSocketConnection, ws_manager

__all__ = [
    "Component",
    "ComponentError",
    "EventNotFoundError",
    "StateSerializer",
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
    "ComponentWebSocketManager",
    "WebSocketConnection",
    "ws_manager",
]

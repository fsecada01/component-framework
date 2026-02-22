"""Framework-agnostic permission classes for component access control."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


class BasePermission:
    """
    Base permission class. All permission classes must inherit from this.

    Subclasses must implement `has_permission`.
    """

    def has_permission(self, request: Any, component_cls: type) -> bool:
        """
        Return True if the request has permission to access the component.

        Args:
            request: The incoming request object.
            component_cls: The component class being accessed.

        Returns:
            True if permission is granted, False otherwise.
        """
        return True


class AllowAny(BasePermission):
    """Allow unrestricted access. Default permission class."""

    def has_permission(self, request: Any, component_cls: type) -> bool:
        return True


class IsAuthenticated(BasePermission):
    """Allow access only to authenticated users."""

    def has_permission(self, request: Any, component_cls: type) -> bool:
        return bool(getattr(request, "user", None) and request.user.is_authenticated)


class IsStaff(BasePermission):
    """Allow access only to staff users."""

    def has_permission(self, request: Any, component_cls: type) -> bool:
        return bool(getattr(request, "user", None) and request.user.is_staff)


class IsSuperuser(BasePermission):
    """Allow access only to superusers."""

    def has_permission(self, request: Any, component_cls: type) -> bool:
        return bool(getattr(request, "user", None) and request.user.is_superuser)


class DjangoModelPermission(BasePermission):
    """
    Allow access based on a specific Django model permission.

    Set `permission_required` on the component class:

        @registry.register("my_component")
        class MyComponent(Component):
            permission_classes = [DjangoModelPermission]
            permission_required = "myapp.change_mymodel"
    """

    def has_permission(self, request: Any, component_cls: type) -> bool:
        permission = getattr(component_cls, "permission_required", "")
        if not permission:
            return True
        user = getattr(request, "user", None)
        if not user:
            return False
        if isinstance(permission, str):
            return user.has_perm(permission)
        # Iterable of permission strings — all must be held
        return all(user.has_perm(p) for p in permission)

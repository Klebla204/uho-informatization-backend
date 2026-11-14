from django.db.models import Q
from django.utils import timezone
from rest_framework.permissions import BasePermission

from .models import RolePermission, UserRole


def user_library_id(user):
    if user.is_superuser or user.tipo_usuario == "SUPER_ADMIN":
        return None
    return user.biblioteca_id


def has_scoped_permission(user, permission_name):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    now = timezone.now()
    assignments = UserRole.objects.filter(
        user=user,
        role__role_permissions__permission__name=permission_name,
        role__role_permissions__allow=True,
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    if user.tipo_usuario == "SUPER_ADMIN":
        return assignments.exists()
    library_id = user_library_id(user)
    if not library_id:
        return False
    return assignments.filter(
        resource_type="biblioteca",
        resource_id=str(library_id),
    ).exists()


class HasRBACManagementPermission(BasePermission):
    message = "Se requiere el rol Super-Admin y el permiso admin.manage."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return UserRole.objects.filter(
            user=user,
            role__name="super_admin",
            role__role_permissions__permission__name="admin.manage",
            role__role_permissions__allow=True,
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        ).exists()


class HasCatalogPermission(BasePermission):
    permission_by_action = {
        "list": "catalogo.view",
        "retrieve": "catalogo.view",
        "create": "catalogo.manage",
        "update": "catalogo.manage",
        "partial_update": "catalogo.manage",
        "destroy": "catalogo.manage",
    }

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True

        permission_name = getattr(view, "required_permission", None)
        if not permission_name:
            permission_name = self.permission_by_action.get(getattr(view, "action", None))
        if not permission_name:
            return False

        return has_scoped_permission(user, permission_name)


class HasLoanManagementPermission(BasePermission):
    message = "Se requiere el permiso prestamos.manage."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return has_scoped_permission(user, "prestamos.manage")

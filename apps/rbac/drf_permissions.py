from django.db.models import Q
from django.utils import timezone
from rest_framework.permissions import BasePermission

from .models import RolePermission, UserRole


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

        return RolePermission.objects.filter(
            role__user_roles__user=user,
            permission__name=permission_name,
            allow=True,
        ).filter(
            Q(role__user_roles__expires_at__isnull=True)
            | Q(role__user_roles__expires_at__gt=timezone.now())
        ).exists()


class HasLoanManagementPermission(BasePermission):
    message = "Se requiere el permiso prestamos.manage."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return RolePermission.objects.filter(
            role__user_roles__user=user,
            permission__name="prestamos.manage",
            allow=True,
        ).filter(
            Q(role__user_roles__expires_at__isnull=True)
            | Q(role__user_roles__expires_at__gt=timezone.now())
        ).exists()

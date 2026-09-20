from rest_framework.permissions import BasePermission

from .models import RolePermission


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
        ).exists()

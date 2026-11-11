from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PermissionCatalogView, RBACAdminViewSet, UserDirectoryView, UserRoleAssignmentViewSet

router = DefaultRouter()
router.register("roles", RBACAdminViewSet, basename="rbac-role")
router.register("asignaciones", UserRoleAssignmentViewSet, basename="rbac-assignment")

urlpatterns = [
    path("permisos/", PermissionCatalogView.as_view(), name="rbac-permissions"),
    path("usuarios/", UserDirectoryView.as_view(), name="rbac-users"),
    path("", include(router.urls)),
]

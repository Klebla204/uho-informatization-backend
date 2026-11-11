from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from .drf_permissions import HasRBACManagementPermission
from .models import Permission, Role, UserRole
from .serializers import PermissionSerializer, RoleSerializer, UserRoleAssignmentSerializer, UserSummarySerializer

User = get_user_model()


class RBACAdminViewSet(viewsets.ModelViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, HasRBACManagementPermission)
    serializer_class = RoleSerializer
    queryset = Role.objects.prefetch_related("role_permissions__permission").order_by("display_name", "name")
    http_method_names = ("get", "post", "patch", "put", "delete", "head", "options")

    def perform_destroy(self, instance):
        if instance.is_system:
            raise ValidationError({"detail": "Los roles predefinidos no se pueden eliminar."})
        if instance.name == "super_admin":
            raise ValidationError({"detail": "El rol Super-Admin no se puede eliminar."})
        instance.delete()


class PermissionCatalogView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, HasRBACManagementPermission)

    def get(self, request):
        permissions = Permission.objects.order_by("name")
        serializer = PermissionSerializer(permissions, many=True)
        modules = {}
        for item in serializer.data:
            modules.setdefault(item["module"], []).append(item)
        return Response({"results": serializer.data, "modules": modules})


class UserRoleAssignmentViewSet(viewsets.ModelViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, HasRBACManagementPermission)
    serializer_class = UserRoleAssignmentSerializer
    queryset = UserRole.objects.select_related("user", "role", "assigned_by").order_by("user__auth_uid", "role__name")
    http_method_names = ("get", "post", "delete", "head", "options")

    def get_queryset(self):
        queryset = super().get_queryset()
        user_id = self.request.query_params.get("user")
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        return queryset

    def perform_destroy(self, instance):
        if instance.role.name == "super_admin":
            active_super_admins = UserRole.objects.filter(
                role=instance.role,
                user__is_active=True,
                user__estado="ACTIVO",
            ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
            if instance.user_id == self.request.user.id or active_super_admins.count() <= 1:
                raise ValidationError({"detail": "No se puede retirar la última asignación activa de Super-Admin ni la propia."})
        instance.delete()


class UserDirectoryView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, HasRBACManagementPermission)

    def get(self, request):
        term = request.query_params.get("q", "").strip()
        users = User.objects.filter(is_active=True, estado="ACTIVO")
        if term:
            users = users.filter(
                Q(auth_uid__icontains=term)
                | Q(nombre__icontains=term)
                | Q(apellidos__icontains=term)
                | Q(email__icontains=term)
            )
        users = users.order_by("auth_uid")[:50]
        return Response(UserSummarySerializer(users, many=True).data)

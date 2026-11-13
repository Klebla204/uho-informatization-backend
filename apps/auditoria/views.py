from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.rbac.models import RolePermission

from .models import LogsAuditoria
from .serializers import AuditLogSerializer


class CanViewAuditLogs(BasePermission):
    message = "Se requiere el permiso auditoria.view."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        now = timezone.now()
        if user.tipo_usuario in {"ADMINISTRADOR", "SUPER_ADMIN"}:
            return True
        return RolePermission.objects.filter(
            role__user_roles__user=user,
            permission__name="auditoria.view",
            allow=True,
        ).filter(
            Q(role__user_roles__expires_at__isnull=True)
            | Q(role__user_roles__expires_at__gt=now)
        ).exists()


class AuditLogListView(ListAPIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, CanViewAuditLogs)
    serializer_class = AuditLogSerializer

    def get_queryset(self):
        queryset = LogsAuditoria.objects.select_related("usuario").order_by("-timestamp")
        action = self.request.query_params.get("accion")
        entity = self.request.query_params.get("entidad")
        user_id = self.request.query_params.get("usuario")
        start_raw = self.request.query_params.get("desde")
        end_raw = self.request.query_params.get("hasta")

        if action:
            queryset = queryset.filter(accion__icontains=action)
        if entity:
            queryset = queryset.filter(entidad__icontains=entity)
        if user_id:
            queryset = queryset.filter(usuario_id=user_id)
        if start_raw:
            start = parse_datetime(start_raw)
            if start is None:
                raise ValidationError({"desde": "Use una fecha ISO 8601 válida."})
            queryset = queryset.filter(timestamp__gte=start)
        if end_raw:
            end = parse_datetime(end_raw)
            if end is None:
                raise ValidationError({"hasta": "Use una fecha ISO 8601 válida."})
            queryset = queryset.filter(timestamp__lte=end)
        return queryset

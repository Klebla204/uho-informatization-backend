from django.db.models import Q
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.rbac.drf_permissions import HasLoanManagementPermission
from apps.users.models import CustomUser

from .models import Prestamo
from .serializers import LoanListSerializer, PendingLoanSerializer, UserLookupSerializer


class MyLoansView(ListAPIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)
    serializer_class = LoanListSerializer

    def get_queryset(self):
        queryset = Prestamo.objects.filter(usuario=self.request.user).select_related(
            "ejemplar__libro", "biblioteca"
        ).order_by("-fecha_solicitud")
        status_filter = self.request.query_params.get("estado")
        valid_statuses = {choice[0] for choice in Prestamo.STATUS_CHOICES}
        if status_filter in valid_statuses:
            queryset = queryset.filter(estado=status_filter)
        return queryset


class PendingLoansView(ListAPIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, HasLoanManagementPermission)
    serializer_class = PendingLoanSerializer

    @extend_schema(
        parameters=[OpenApiParameter("biblioteca", str, description="UUID de biblioteca para filtrar")],
    )
    def get_queryset(self):
        queryset = Prestamo.objects.filter(estado="PENDIENTE").select_related(
            "usuario", "ejemplar__libro", "biblioteca"
        ).order_by("fecha_solicitud")
        library_id = self.request.query_params.get("biblioteca")
        if library_id:
            queryset = queryset.filter(biblioteca_id=library_id)
        return queryset


class ActiveLoansView(ListAPIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, HasLoanManagementPermission)
    serializer_class = PendingLoanSerializer

    def get_queryset(self):
        return Prestamo.objects.filter(
            estado__in=["APROBADO", "LISTO", "ACTIVO", "VENCIDO"]
        ).select_related("usuario", "ejemplar__libro", "biblioteca").order_by("fecha_devolucion_pactada")


class UserLookupView(ListAPIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, HasLoanManagementPermission)
    serializer_class = UserLookupSerializer

    @extend_schema(parameters=[OpenApiParameter("q", str, description="Usuario, nombre o apellidos")])
    def get_queryset(self):
        term = self.request.query_params.get("q", "").strip()
        if not term:
            return CustomUser.objects.none()
        return CustomUser.objects.filter(
            Q(auth_uid__icontains=term) | Q(nombre__icontains=term) | Q(apellidos__icontains=term),
            is_active=True,
            estado="ACTIVO",
        ).order_by("auth_uid")[:10]

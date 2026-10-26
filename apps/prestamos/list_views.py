from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.rbac.drf_permissions import HasLoanManagementPermission

from .models import Prestamo
from .serializers import LoanListSerializer, PendingLoanSerializer


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

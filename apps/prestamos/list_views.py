from uuid import UUID

from django.db.models import Q
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiParameter
from rest_framework import serializers
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.rbac.drf_permissions import HasLoanManagementPermission
from apps.users.models import CustomUser

from .models import Notificacion, Prestamo
from .serializers import (
    LoanListSerializer,
    NotificationSerializer,
    PendingLoanSerializer,
    UserLookupSerializer,
)
from .vencimientos import due_windows, notify_due_loans


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


class RequestsInProgressView(ListAPIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, HasLoanManagementPermission)
    serializer_class = PendingLoanSerializer

    def get_queryset(self):
        return Prestamo.objects.filter(
            estado__in=["PENDIENTE", "APROBADO", "LISTO"]
        ).select_related("usuario", "ejemplar__libro", "biblioteca").order_by("fecha_solicitud")


class ActiveLoansView(ListAPIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, HasLoanManagementPermission)
    serializer_class = PendingLoanSerializer

    def get_queryset(self):
        return Prestamo.objects.filter(
            estado__in=["ACTIVO", "VENCIDO"]
        ).select_related("usuario", "ejemplar__libro", "biblioteca").order_by("fecha_devolucion_pactada")


class DueLoansView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, HasLoanManagementPermission)

    @extend_schema(
        responses=inline_serializer(
            "DueLoans",
            {"proximos": PendingLoanSerializer(many=True), "vencidos": PendingLoanSerializer(many=True)},
        )
    )
    def get(self, request):
        start_today, window_end = due_windows()
        active = Prestamo.objects.filter(estado="ACTIVO").select_related("usuario", "ejemplar__libro", "biblioteca")
        upcoming = active.filter(fecha_devolucion_pactada__gte=start_today, fecha_devolucion_pactada__lt=window_end)
        overdue = active.filter(fecha_devolucion_pactada__lt=start_today)
        return Response({
            "proximos": PendingLoanSerializer(upcoming.order_by("fecha_devolucion_pactada"), many=True).data,
            "vencidos": PendingLoanSerializer(overdue.order_by("fecha_devolucion_pactada"), many=True).data,
        })


class MyNotificationsView(ListAPIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)
    serializer_class = NotificationSerializer

    def get_queryset(self):
        notify_due_loans(user=self.request.user)
        return Notificacion.objects.filter(usuario=self.request.user).order_by("-fecha_envio")


class MarkNotificationReadView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    @extend_schema(request=None, responses=inline_serializer("MarkRead", {"actualizadas": serializers.IntegerField()}))
    def post(self, request, notification_id=None):
        queryset = Notificacion.objects.filter(usuario=request.user, leida=False)
        if notification_id:
            queryset = queryset.filter(id=notification_id)
        return Response({"actualizadas": queryset.update(leida=True)})


class UserLookupView(ListAPIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, HasLoanManagementPermission)
    serializer_class = UserLookupSerializer

    @extend_schema(parameters=[OpenApiParameter("q", str, description="Usuario, nombre, apellidos, CI o ID del código QR")])
    def get_queryset(self):
        term = self.request.query_params.get("q", "").strip()
        if not term:
            return CustomUser.objects.none()
        active = CustomUser.objects.filter(is_active=True, estado="ACTIVO")
        try:
            return active.filter(id=UUID(term))
        except ValueError:
            pass
        if term.isdigit():
            # El CI está cifrado en base de datos, por lo que se compara en memoria.
            ids = [user.id for user in active if user.ci == term][:10]
            return active.filter(id__in=ids)
        return active.filter(
            Q(auth_uid__icontains=term) | Q(nombre__icontains=term) | Q(apellidos__icontains=term)
        ).order_by("auth_uid")[:10]

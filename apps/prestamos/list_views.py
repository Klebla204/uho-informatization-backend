from uuid import UUID

from django.db.models import Q
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiParameter
from rest_framework import serializers
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.rbac.drf_permissions import HasLoanManagementPermission
from apps.rbac.drf_permissions import user_library_id
from apps.users.models import CustomUser

from .models import Notificacion, Prestamo
from .models import Sancion
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

    @extend_schema(
        summary="Consultar estado de mis préstamos",
        description="Devuelve únicamente los préstamos del usuario autenticado, con estado, libro, ejemplar, biblioteca y fechas. Requiere JWT Bearer.",
        parameters=[
            OpenApiParameter(
                "estado",
                OpenApiTypes.STR,
                enum=[choice[0] for choice in Prestamo.STATUS_CHOICES],
                description="Filtra por estado del préstamo.",
            ),
        ],
        responses=LoanListSerializer(many=True),
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

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
        assigned_library = user_library_id(self.request.user)
        if assigned_library:
            queryset = queryset.filter(biblioteca_id=assigned_library)
        library_id = self.request.query_params.get("biblioteca")
        if library_id:
            queryset = queryset.filter(biblioteca_id=library_id)
        return queryset


class RequestsInProgressView(ListAPIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, HasLoanManagementPermission)
    serializer_class = PendingLoanSerializer

    def get_queryset(self):
        queryset = Prestamo.objects.filter(
            estado__in=["PENDIENTE", "APROBADO", "LISTO"]
        ).select_related("usuario", "ejemplar__libro", "biblioteca").order_by("fecha_solicitud")
        assigned_library = user_library_id(self.request.user)
        return queryset.filter(biblioteca_id=assigned_library) if assigned_library else queryset


class ActiveLoansView(ListAPIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, HasLoanManagementPermission)
    serializer_class = PendingLoanSerializer

    def get_queryset(self):
        queryset = Prestamo.objects.filter(
            estado__in=["ACTIVO", "VENCIDO"]
        ).select_related("usuario", "ejemplar__libro", "biblioteca").order_by("fecha_devolucion_pactada")
        assigned_library = user_library_id(self.request.user)
        return queryset.filter(biblioteca_id=assigned_library) if assigned_library else queryset


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
        assigned_library = user_library_id(request.user)
        if assigned_library:
            active = active.filter(biblioteca_id=assigned_library)
        upcoming = active.filter(fecha_devolucion_pactada__gte=start_today, fecha_devolucion_pactada__lt=window_end)
        overdue = active.filter(fecha_devolucion_pactada__lt=start_today)
        return Response({
            "proximos": PendingLoanSerializer(upcoming.order_by("fecha_devolucion_pactada"), many=True).data,
            "vencidos": PendingLoanSerializer(overdue.order_by("fecha_devolucion_pactada"), many=True).data,
        })


class SanctionsView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, HasLoanManagementPermission)

    def get(self, request):
        assigned_library = user_library_id(request.user)
        overdue = Prestamo.objects.filter(
            estado="ACTIVO",
            fecha_devolucion_pactada__lt=due_windows()[0],
            usuario__is_active=True,
        ).exclude(
            usuario__estado="INACTIVO",
        ).select_related("usuario", "ejemplar__libro", "biblioteca").exclude(
            usuario__sanciones__activa=True
        ).order_by("fecha_devolucion_pactada")
        sanctions = Sancion.objects.filter(activa=True).select_related(
            "usuario", "prestamo__ejemplar__libro", "prestamo__biblioteca"
        ).order_by("fecha_sancion")
        if assigned_library:
            overdue = overdue.filter(biblioteca_id=assigned_library)
            sanctions = sanctions.filter(prestamo__biblioteca_id=assigned_library)

        def loan_data(loan):
            return {
                "id": str(loan.id),
                "usuario_id": str(loan.usuario_id),
                "usuario_nombre": str(loan.usuario),
                "usuario_uid": loan.usuario.auth_uid,
                "libro_titulo": loan.ejemplar.libro.titulo,
                "biblioteca_nombre": loan.biblioteca.nombre,
                "fecha_devolucion_pactada": loan.fecha_devolucion_pactada,
                "dias_vencido": max(1, (timezone.localtime().date() - timezone.localtime(loan.fecha_devolucion_pactada).date()).days),
            }

        return Response({
            "vencidos": [loan_data(loan) for loan in overdue],
            "sancionados": [{
                **loan_data(sanction.prestamo),
                "sancion_id": str(sanction.id),
                "fecha_sancion": sanction.fecha_sancion,
                "motivo": sanction.motivo,
            } for sanction in sanctions],
        })

    def post(self, request):
        from .services import SanctionError, register_sanction

        loan_id = request.data.get("prestamo")
        loan = Prestamo.objects.filter(id=loan_id).select_related("biblioteca").first()
        if loan is None:
            return Response({"detail": "El préstamo no existe."}, status=404)
        assigned_library = user_library_id(request.user)
        if assigned_library and loan.biblioteca_id != assigned_library:
            return Response({"detail": "Solo puedes gestionar sanciones de tu sede."}, status=403)
        try:
            sanction = register_sanction(
                loan_id=loan.id,
                librarian=request.user,
                reason=str(request.data.get("motivo", ""))[:2000],
            )
        except SanctionError as error:
            return Response({"detail": str(error)}, status=409)
        return Response({"id": str(sanction.id), "usuario": str(sanction.usuario_id)}, status=201)


class UnblockUserView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, HasLoanManagementPermission)

    def post(self, request, sanction_id):
        from .services import SanctionError, unblock_user

        sanction = Sancion.objects.filter(id=sanction_id, activa=True).select_related("prestamo__biblioteca").first()
        if sanction is None:
            return Response({"detail": "La sanción activa no existe."}, status=404)
        assigned_library = user_library_id(request.user)
        if assigned_library and sanction.prestamo.biblioteca_id != assigned_library:
            return Response({"detail": "Solo puedes gestionar sanciones de tu sede."}, status=403)
        try:
            unblock_user(sanction_id=sanction.id, librarian=request.user)
        except SanctionError as error:
            return Response({"detail": str(error)}, status=409)
        return Response({"detail": "Usuario desbloqueado."})


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
        assigned_library = user_library_id(self.request.user)
        if assigned_library:
            active = active.filter(
                Q(tipo_usuario__in=["ESTUDIANTE", "TRABAJADOR"])
                | Q(biblioteca_id=assigned_library)
            )
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

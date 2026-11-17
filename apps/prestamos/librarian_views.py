from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.rbac.drf_permissions import HasLoanManagementPermission, user_library_id
from apps.catalogo.models import Biblioteca
from apps.users.models import CustomUser

from .librarian_serializers import (
    ApproveLoanSerializer,
    CollectLoanSerializer,
    CounterLoanSerializer,
    LoanActionResponseSerializer,
    RejectLoanSerializer,
    RenewalDecisionSerializer,
)
from .librarian_services import (
    LibrarianLoanError,
    approve_loan,
    collect_loan,
    mark_loan_ready,
    reject_loan,
    return_loan,
    decide_renewal,
)
from .models import RenovacionPrestamo
from .serializers import LoanResponseSerializer, RenewalRequestSerializer
from .services import LoanRequestError, create_counter_loan


class LibrarianLoanActionView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, HasLoanManagementPermission)

    def _execute(self, action, request, loan_id, **kwargs):
        try:
            loan = action(loan_id=loan_id, librarian=request.user, **kwargs)
        except LibrarianLoanError as error:
            return Response({"detail": str(error)}, status=status.HTTP_409_CONFLICT)
        return Response(LoanResponseSerializer(loan).data, status=status.HTTP_200_OK)


class ApproveLoanView(LibrarianLoanActionView):
    @extend_schema(request=ApproveLoanSerializer, responses=LoanActionResponseSerializer)
    def post(self, request, loan_id):
        serializer = ApproveLoanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._execute(approve_loan, request, loan_id, pickup_deadline=serializer.validated_data.get("fecha_recogida_limite"))


class RejectLoanView(LibrarianLoanActionView):
    @extend_schema(request=RejectLoanSerializer, responses=LoanActionResponseSerializer)
    def post(self, request, loan_id):
        serializer = RejectLoanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._execute(reject_loan, request, loan_id, reason=serializer.validated_data["motivo"])


class MarkLoanReadyView(LibrarianLoanActionView):
    @extend_schema(request=ApproveLoanSerializer, responses=LoanActionResponseSerializer)
    def post(self, request, loan_id):
        serializer = ApproveLoanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not serializer.validated_data.get("fecha_recogida_limite"):
            return Response({"detail": "La fecha límite de recojo es obligatoria."}, status=status.HTTP_400_BAD_REQUEST)
        return self._execute(mark_loan_ready, request, loan_id, pickup_deadline=serializer.validated_data["fecha_recogida_limite"])


class CollectLoanView(LibrarianLoanActionView):
    @extend_schema(request=CollectLoanSerializer, responses=LoanActionResponseSerializer)
    def post(self, request, loan_id):
        serializer = CollectLoanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._execute(
            collect_loan,
            request,
            loan_id,
            due_date=serializer.validated_data["fecha_devolucion_pactada"],
        )


class ReturnLoanView(LibrarianLoanActionView):
    @extend_schema(request=None, responses=LoanActionResponseSerializer)
    def post(self, request, loan_id):
        return self._execute(return_loan, request, loan_id)


class RenewalQueueView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, HasLoanManagementPermission)

    @extend_schema(responses=RenewalRequestSerializer(many=True))
    def get(self, request):
        renewals = RenovacionPrestamo.objects.filter(estado="PENDIENTE").select_related(
            "prestamo__ejemplar__libro", "prestamo__biblioteca", "prestamo__usuario"
        ).order_by("fecha_solicitud")
        assigned_library = user_library_id(request.user)
        if assigned_library:
            renewals = renewals.filter(prestamo__biblioteca_id=assigned_library)
        return Response(RenewalRequestSerializer(renewals, many=True).data)

    @extend_schema(request=RenewalDecisionSerializer, responses=RenewalRequestSerializer)
    def post(self, request, renewal_id):
        serializer = RenewalDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        approve = "fecha_devolucion_pactada" in serializer.validated_data
        try:
            renewal = decide_renewal(
                renewal_id=renewal_id,
                librarian=request.user,
                approve=approve,
                due_date=serializer.validated_data.get("fecha_devolucion_pactada"),
                reason=serializer.validated_data.get("motivo", ""),
            )
        except LibrarianLoanError as error:
            return Response({"detail": str(error)}, status=status.HTTP_409_CONFLICT)
        return Response(RenewalRequestSerializer(renewal).data)


class CounterLoanView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, HasLoanManagementPermission)

    @extend_schema(request=CounterLoanSerializer, responses=LoanResponseSerializer)
    def post(self, request):
        serializer = CounterLoanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = CustomUser.objects.filter(id=data["usuario"], is_active=True, estado="ACTIVO").first()
        library = Biblioteca.objects.filter(id=data["biblioteca"], activa=True).first()
        if user is None:
            return Response({"detail": "El usuario no existe o no está activo."}, status=status.HTTP_404_NOT_FOUND)
        if library is None:
            return Response({"detail": "La biblioteca no existe o está inactiva."}, status=status.HTTP_404_NOT_FOUND)
        if request.user.biblioteca_id and request.user.biblioteca_id != library.id:
            return Response({"detail": "Solo puedes registrar préstamos para tu sede."}, status=status.HTTP_403_FORBIDDEN)
        try:
            loan = create_counter_loan(
                user=user,
                librarian=request.user,
                book_id=data["libro"],
                library_id=library.id,
                due_date=data["fecha_devolucion_pactada"],
                observations=data.get("observaciones", ""),
            )
        except LoanRequestError as error:
            return Response({"detail": str(error)}, status=status.HTTP_409_CONFLICT)
        return Response(LoanResponseSerializer(loan).data, status=status.HTTP_201_CREATED)

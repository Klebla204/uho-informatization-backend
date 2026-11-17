from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import ListaEspera, RenovacionPrestamo
from .serializers import (
    LoanRequestSerializer,
    LoanResponseSerializer,
    RenewalRequestSerializer,
    WaitingListEntrySerializer,
    WaitingListJoinSerializer,
)
from .services import (
    LoanRequestError,
    RenewalError,
    WaitingListError,
    join_waiting_list,
    request_loan,
    request_renewal,
)


class LoanRequestView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    @extend_schema(request=LoanRequestSerializer, responses=LoanResponseSerializer)
    def post(self, request):
        serializer = LoanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            loan = request_loan(
                user=request.user,
                book_id=serializer.validated_data["libro"],
                library_id=serializer.validated_data.get("biblioteca"),
                observations=serializer.validated_data.get("observaciones", ""),
            )
        except LoanRequestError as error:
            return Response({"detail": str(error)}, status=status.HTTP_409_CONFLICT)

        return Response(LoanResponseSerializer(loan).data, status=status.HTTP_201_CREATED)


class WaitingListView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=WaitingListEntrySerializer(many=True))
    def get(self, request):
        entries = ListaEspera.objects.filter(usuario=request.user).select_related("libro").order_by(
            "fecha_inscripcion", "id"
        )
        book_id = request.query_params.get("libro")
        if book_id:
            entries = entries.filter(libro_id=book_id)
        return Response(WaitingListEntrySerializer(entries, many=True).data)

    @extend_schema(request=WaitingListJoinSerializer, responses=WaitingListEntrySerializer)
    def post(self, request):
        serializer = WaitingListJoinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            entry, created = join_waiting_list(
                user=request.user,
                book_id=serializer.validated_data["libro"],
            )
        except WaitingListError as error:
            return Response({"detail": str(error)}, status=status.HTTP_409_CONFLICT)
        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(WaitingListEntrySerializer(entry).data, status=response_status)


class RenewalRequestView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=RenewalRequestSerializer(many=True))
    def get(self, request):
        renewals = RenewalRequestSerializer(
            RenovacionPrestamo.objects.filter(prestamo__usuario=request.user)
            .select_related("prestamo__ejemplar__libro", "prestamo__biblioteca", "prestamo__usuario")
            .order_by("-fecha_solicitud"),
            many=True,
        )
        return Response(renewals.data)

    @extend_schema(responses=RenewalRequestSerializer)
    def post(self, request, loan_id):
        try:
            renewal = request_renewal(user=request.user, loan_id=loan_id)
        except RenewalError as error:
            return Response({"detail": str(error)}, status=status.HTTP_409_CONFLICT)
        return Response(RenewalRequestSerializer(renewal).data, status=status.HTTP_201_CREATED)

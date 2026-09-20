from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from .librarian_serializers import (
    ApproveLoanSerializer,
    LoanActionResponseSerializer,
    RejectLoanSerializer,
)
from .librarian_services import (
    LibrarianLoanError,
    approve_loan,
    collect_loan,
    mark_loan_ready,
    reject_loan,
    return_loan,
)
from .serializers import LoanResponseSerializer


class LibrarianLoanActionView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

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
    @extend_schema(request=None, responses=LoanActionResponseSerializer)
    def post(self, request, loan_id):
        return self._execute(collect_loan, request, loan_id)


class ReturnLoanView(LibrarianLoanActionView):
    @extend_schema(request=None, responses=LoanActionResponseSerializer)
    def post(self, request, loan_id):
        return self._execute(return_loan, request, loan_id)

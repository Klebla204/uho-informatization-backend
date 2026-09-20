from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from .serializers import LoanRequestSerializer, LoanResponseSerializer
from .services import LoanRequestError, request_loan


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
                due_date=serializer.validated_data["fecha_devolucion_pactada"],
                observations=serializer.validated_data.get("observaciones", ""),
            )
        except LoanRequestError as error:
            return Response({"detail": str(error)}, status=status.HTTP_409_CONFLICT)

        return Response(LoanResponseSerializer(loan).data, status=status.HTTP_201_CREATED)

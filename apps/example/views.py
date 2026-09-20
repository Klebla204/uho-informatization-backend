from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers


class HelloUHO(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses=inline_serializer(
            name="HelloResponse",
            fields={"message": serializers.CharField()},
        )
    )
    def get(self, request):
        return Response({"message": f"Hola {request.user.username}, bienvenido al sistema UHO"})


class HealthCheckView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        responses=inline_serializer(
            name="HealthResponse",
            fields={
                "status": serializers.CharField(),
                "service": serializers.CharField(),
                "timestamp": serializers.DateTimeField(),
            },
        )
    )
    def get(self, request):
        return Response({
            "status": "ok",
            "service": "uho-backend",
            "timestamp": timezone.now().isoformat(),
        })

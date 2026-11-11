from django.contrib.auth import authenticate, get_user_model
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.rbac.models import UserRole
from .client import uho_login

User = get_user_model()


def _map_user_type(value):
    text = (value or "").lower()
    if "estud" in text or "student" in text:
        return "ESTUDIANTE"
    return "TRABAJADOR"


class LoginView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
        failed = Response({"error": "Login failed"}, status=status.HTTP_401_UNAUTHORIZED)

        if not username or not password:
            return failed

        # 1) Usuario local (p. ej. superusuarios creados en Django)
        user = authenticate(username=username, password=password)

        # 2) Si no es local, validar contra la universidad
        if user is None:
            data = uho_login(username, password)
            if data is None or not data["active"]:
                return failed

            uid = data["username"] or username
            user = User.objects.filter(auth_uid=uid).first()
            if user is None:
                user = User.objects.create_user(
                    auth_uid=uid,
                    email=f"{uid}@uho.edu.cu",
                    nombre=data["name"] or "",
                    apellidos=data["surname"] or "",
                    ci=data["national_id"] or uid,
                    tipo_usuario=_map_user_type(data["user_type"]),
                )

        if not user.is_active or user.estado != "ACTIVO":
            return failed

        refresh = RefreshToken.for_user(user)
        active_roles = list(UserRole.objects.filter(user=user).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        ).values_list("role__name", flat=True))
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "username": user.auth_uid,
            "nombre": user.nombre,
            "apellidos": user.apellidos,
            "tipo_usuario": user.tipo_usuario,
            "is_staff": user.is_staff,
            "roles": active_roles,
        })

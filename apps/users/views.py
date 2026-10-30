from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication


def _mask_ci(ci):
    return f"{ci[:4]}{'●' * max(len(ci) - 4, 0)}" if ci else ""


def _academic_profile(user):
    student = getattr(user, "perfil_estudiante", None)
    if student:
        return {
            "carrera": student.carrera.nombre,
            "facultad": student.facultad.nombre,
            "anio": student.anio,
            "tipo_curso": student.tipo_curso,
        }
    worker = getattr(user, "perfil_trabajador", None)
    if worker:
        return {"cargo": worker.cargo.nombre, "departamento": worker.departamento, "tipo_contrato": worker.tipo_contrato}
    return None


class MyProfileView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def _data(self, user):
        return {
            "usuario": user.auth_uid,
            "nombre": user.nombre,
            "apellidos": user.apellidos,
            "email": user.email,
            "ci": _mask_ci(user.ci),
            "telefono": user.telefono,
            "tipo_usuario": user.tipo_usuario,
            "perfil": _academic_profile(user),
        }

    @extend_schema(responses=inline_serializer("MyProfile", {"usuario": serializers.CharField()}))
    def get(self, request):
        return Response(self._data(request.user))

    @extend_schema(
        request=inline_serializer("MyProfileUpdate", {"telefono": serializers.CharField(max_length=30)}),
        responses=inline_serializer("MyProfileUpdated", {"usuario": serializers.CharField()}),
    )
    def patch(self, request):
        phone = serializers.CharField(max_length=30, allow_blank=True)
        user = request.user
        user.telefono = phone.run_validation(request.data.get("telefono", user.telefono))
        user.save(update_fields=["telefono"])
        return Response(self._data(user))


class MyCardView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=inline_serializer("MyCard", {"codigo_qr": serializers.CharField()}))
    def get(self, request):
        user = request.user
        profile = _academic_profile(user) or {}
        return Response({
            "id": str(user.id),
            "nombre_completo": f"{user.nombre} {user.apellidos}".strip(),
            "ci": user.ci,
            "tipo_usuario": user.tipo_usuario,
            "carrera": profile.get("carrera"),
            "facultad": profile.get("facultad"),
            "codigo_qr": str(user.id),
        })

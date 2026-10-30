from django.db import transaction
from django.http import HttpResponse
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.academics.models import Carrera, Facultad
from apps.students.models import PerfilEstudiante

from .carnet import (
    USER_TYPE_LABELS,
    academic_profile,
    build_carnet_pdf,
    ensure_carnet,
    profile_complete,
    qr_svg,
)

INCOMPLETE_PROFILE = "Completa tu perfil para generar tu carnet."


class ProfileUpdateSerializer(serializers.Serializer):
    nombre = serializers.CharField(max_length=150, required=False)
    apellidos = serializers.CharField(max_length=200, required=False)
    ci = serializers.CharField(max_length=20, required=False)
    telefono = serializers.CharField(max_length=30, required=False)
    facultad = serializers.UUIDField(required=False)
    carrera = serializers.UUIDField(required=False)
    anio = serializers.IntegerField(min_value=1, max_value=10, required=False)
    tipo_curso = serializers.CharField(max_length=100, required=False)


class MyProfileView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def _data(self, user):
        profile = academic_profile(user)
        student = getattr(user, "perfil_estudiante", None)
        if profile and student:
            profile.update({"facultad_id": str(student.facultad_id), "carrera_id": str(student.carrera_id)})
        return {
            "usuario": user.auth_uid,
            "nombre": user.nombre,
            "apellidos": user.apellidos,
            "email": user.email,
            "ci": user.ci,
            "telefono": user.telefono,
            "tipo_usuario": user.tipo_usuario,
            "perfil": profile,
            "perfil_completo": profile_complete(user),
        }

    @extend_schema(responses=inline_serializer("MyProfile", {"usuario": serializers.CharField()}))
    def get(self, request):
        return Response(self._data(request.user))

    @extend_schema(
        request=ProfileUpdateSerializer,
        responses=inline_serializer("MyProfileUpdated", {"usuario": serializers.CharField()}),
    )
    def patch(self, request):
        serializer = ProfileUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = request.user

        academic_keys = ("facultad", "carrera", "anio", "tipo_curso")
        student = getattr(user, "perfil_estudiante", None)
        if user.tipo_usuario == "ESTUDIANTE" and any(key in data for key in academic_keys):
            merged = {
                "facultad": data.get("facultad") or (student and student.facultad_id),
                "carrera": data.get("carrera") or (student and student.carrera_id),
                "anio": data.get("anio") or (student and student.anio),
                "tipo_curso": data.get("tipo_curso") or (student and student.tipo_curso),
            }
            missing = [key for key, value in merged.items() if not value]
            if missing:
                return Response(
                    {key: ["Este campo es obligatorio."] for key in missing},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            faculty = Facultad.objects.filter(id=merged["facultad"], activa=True).first()
            career = Carrera.objects.filter(id=merged["carrera"], activa=True).first()
            if faculty is None or career is None or career.facultad_id != faculty.id:
                return Response(
                    {"carrera": ["La carrera no pertenece a la facultad elegida."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        with transaction.atomic():
            for field in ("nombre", "apellidos", "ci", "telefono"):
                if field in data:
                    setattr(user, field, data[field].strip())
            user.save(update_fields=[f for f in ("nombre", "apellidos", "ci", "telefono") if f in data] or None)

            if user.tipo_usuario == "ESTUDIANTE" and any(key in data for key in academic_keys):
                PerfilEstudiante.objects.update_or_create(
                    usuario=user,
                    defaults={
                        "facultad": faculty,
                        "carrera": career,
                        "anio": merged["anio"],
                        "tipo_curso": merged["tipo_curso"],
                    },
                    create_defaults={
                        "facultad": faculty,
                        "carrera": career,
                        "anio": merged["anio"],
                        "tipo_curso": merged["tipo_curso"],
                        "matricula": user.auth_uid,
                    },
                )
                user = type(user).objects.get(pk=user.pk)

            if profile_complete(user):
                ensure_carnet(user)

        return Response(self._data(user))


class FacultySerializer(serializers.ModelSerializer):
    class Meta:
        model = Facultad
        fields = ("id", "nombre")


class CareerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Carrera
        fields = ("id", "nombre")


class FacultyListView(ListAPIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)
    pagination_class = None
    serializer_class = FacultySerializer

    def get_queryset(self):
        return Facultad.objects.filter(activa=True).order_by("nombre")


class CareerListView(ListAPIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)
    pagination_class = None
    serializer_class = CareerSerializer

    def get_queryset(self):
        queryset = Carrera.objects.filter(activa=True).order_by("nombre")
        faculty = self.request.query_params.get("facultad")
        return queryset.filter(facultad_id=faculty) if faculty else queryset


class MyCardView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=inline_serializer("MyCard", {"codigo_qr": serializers.CharField()}))
    def get(self, request):
        user = request.user
        if not profile_complete(user):
            return Response({"detail": INCOMPLETE_PROFILE}, status=status.HTTP_409_CONFLICT)
        carnet = ensure_carnet(user)
        profile = academic_profile(user) or {}
        return Response({
            "id": str(user.id),
            "nombre_completo": f"{user.nombre} {user.apellidos}".strip(),
            "ci": user.ci,
            "telefono": user.telefono,
            "tipo_usuario": user.tipo_usuario,
            "tipo_usuario_etiqueta": USER_TYPE_LABELS.get(user.tipo_usuario, user.tipo_usuario),
            "carrera": profile.get("carrera"),
            "facultad": profile.get("facultad"),
            "anio": profile.get("anio"),
            "tipo_curso": profile.get("tipo_curso"),
            "codigo_qr": carnet.codigo_qr,
            "qr_svg": qr_svg(carnet.codigo_qr),
        })


class MyCardPdfView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses={(200, "application/pdf"): bytes})
    def get(self, request):
        user = request.user
        if not profile_complete(user):
            return Response({"detail": INCOMPLETE_PROFILE}, status=status.HTTP_409_CONFLICT)
        carnet = ensure_carnet(user)
        response = HttpResponse(build_carnet_pdf(user, carnet.codigo_qr), content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="carnet-biblio-uho.pdf"'
        return response

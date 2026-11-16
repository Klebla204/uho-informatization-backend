from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.rbac.drf_permissions import HasRBACManagementPermission
from apps.academics.models import Carrera, Facultad
from apps.hr.models import Cargo


class FacultyCrudSerializer(serializers.ModelSerializer):
    class Meta:
        model = Facultad
        fields = ("id", "nombre", "codigo", "decano", "activa")
        read_only_fields = ("id",)


class CareerCrudSerializer(serializers.ModelSerializer):
    facultad_nombre = serializers.CharField(source="facultad.nombre", read_only=True)

    class Meta:
        model = Carrera
        fields = ("id", "nombre", "codigo", "facultad", "facultad_nombre", "activa")
        read_only_fields = ("id", "facultad_nombre")


class CargoCrudSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cargo
        fields = ("id", "nombre", "nivel", "activa")
        read_only_fields = ("id",)


class SuperAdminCrudViewSet(ModelViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, HasRBACManagementPermission)


class FacultyCrudViewSet(SuperAdminCrudViewSet):
    queryset = Facultad.objects.all().order_by("nombre")
    serializer_class = FacultyCrudSerializer

    def perform_destroy(self, instance):
        instance.activa = False
        instance.save(update_fields=("activa",))


class CareerCrudViewSet(SuperAdminCrudViewSet):
    queryset = Carrera.objects.select_related("facultad").all().order_by("nombre")
    serializer_class = CareerCrudSerializer

    def perform_destroy(self, instance):
        instance.activa = False
        instance.save(update_fields=("activa",))


class CargoCrudViewSet(SuperAdminCrudViewSet):
    queryset = Cargo.objects.all().order_by("nombre")
    serializer_class = CargoCrudSerializer

    def perform_destroy(self, instance):
        instance.activa = False
        instance.save(update_fields=("activa",))

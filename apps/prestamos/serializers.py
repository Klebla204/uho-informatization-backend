from rest_framework import serializers

from apps.users.models import CustomUser

from .models import Notificacion, Prestamo
from .vencimientos import days_until_due


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notificacion
        fields = ("id", "tipo", "mensaje", "leida", "fecha_envio", "prestamo")
        read_only_fields = fields


class UserLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ("id", "auth_uid", "nombre", "apellidos", "tipo_usuario")


class LoanRequestSerializer(serializers.Serializer):
    libro = serializers.UUIDField()
    biblioteca = serializers.UUIDField()
    observaciones = serializers.CharField(required=False, allow_blank=True)


class LoanResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prestamo
        fields = (
            "id",
            "usuario",
            "ejemplar",
            "biblioteca",
            "bibliotecario",
            "fecha_solicitud",
            "fecha_devolucion_pactada",
            "estado",
            "observaciones",
        )
        read_only_fields = fields


class LoanListSerializer(serializers.ModelSerializer):
    libro_titulo = serializers.CharField(source="ejemplar.libro.titulo", read_only=True)
    codigo_ejemplar = serializers.CharField(source="ejemplar.codigo_ejemplar", read_only=True)
    biblioteca_nombre = serializers.CharField(source="biblioteca.nombre", read_only=True)
    dias_restantes = serializers.SerializerMethodField()
    vencido = serializers.SerializerMethodField()

    def get_dias_restantes(self, loan) -> int | None:
        return days_until_due(loan) if loan.estado == "ACTIVO" else None

    def get_vencido(self, loan) -> bool:
        return loan.estado == "ACTIVO" and days_until_due(loan) < 0

    class Meta:
        model = Prestamo
        fields = (
            "id",
            "libro_titulo",
            "ejemplar",
            "codigo_ejemplar",
            "biblioteca",
            "biblioteca_nombre",
            "fecha_solicitud",
            "fecha_aprobacion",
            "fecha_recogida_limite",
            "fecha_devolucion_pactada",
            "fecha_devolucion_real",
            "estado",
            "dias_restantes",
            "vencido",
            "observaciones",
        )


class PendingLoanSerializer(LoanListSerializer):
    usuario_nombre = serializers.SerializerMethodField()
    usuario_tipo = serializers.CharField(source="usuario.tipo_usuario", read_only=True)

    class Meta(LoanListSerializer.Meta):
        fields = LoanListSerializer.Meta.fields + ("usuario", "usuario_nombre", "usuario_tipo")

    def get_usuario_nombre(self, loan) -> str:
        return f"{loan.usuario.nombre} {loan.usuario.apellidos}".strip()

from rest_framework import serializers

from .models import Prestamo


class LoanRequestSerializer(serializers.Serializer):
    libro = serializers.UUIDField()
    biblioteca = serializers.UUIDField(required=False, allow_null=True)
    fecha_devolucion_pactada = serializers.DateTimeField()
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
            "observaciones",
        )


class PendingLoanSerializer(LoanListSerializer):
    usuario_nombre = serializers.SerializerMethodField()
    usuario_tipo = serializers.CharField(source="usuario.tipo_usuario", read_only=True)

    class Meta(LoanListSerializer.Meta):
        fields = LoanListSerializer.Meta.fields + ("usuario", "usuario_nombre", "usuario_tipo")

    def get_usuario_nombre(self, loan) -> str:
        return f"{loan.usuario.nombre} {loan.usuario.apellidos}".strip()

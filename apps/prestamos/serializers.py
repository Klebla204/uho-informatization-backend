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

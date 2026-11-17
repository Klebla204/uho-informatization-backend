from rest_framework import serializers


class ApproveLoanSerializer(serializers.Serializer):
    fecha_recogida_limite = serializers.DateTimeField(required=False, allow_null=True)


class RejectLoanSerializer(serializers.Serializer):
    motivo = serializers.CharField(required=True, allow_blank=False)


class RenewalDecisionSerializer(serializers.Serializer):
    fecha_devolucion_pactada = serializers.DateTimeField(required=False)
    motivo = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        has_due_date = "fecha_devolucion_pactada" in attrs
        has_reason = bool(attrs.get("motivo", "").strip())
        if has_due_date == has_reason:
            raise serializers.ValidationError(
                "Indica una nueva fecha para aprobar o un motivo para rechazar."
            )
        return attrs


class CollectLoanSerializer(serializers.Serializer):
    fecha_devolucion_pactada = serializers.DateTimeField()


class CounterLoanSerializer(serializers.Serializer):
    usuario = serializers.UUIDField()
    libro = serializers.UUIDField()
    biblioteca = serializers.UUIDField()
    fecha_devolucion_pactada = serializers.DateTimeField()
    observaciones = serializers.CharField(required=False, allow_blank=True)


class LoanActionResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    estado = serializers.CharField()
    ejemplar = serializers.UUIDField()
    biblioteca = serializers.UUIDField()
    fecha_aprobacion = serializers.DateTimeField(allow_null=True)
    fecha_recogida_limite = serializers.DateTimeField(allow_null=True)
    fecha_devolucion_real = serializers.DateTimeField(allow_null=True)
    observaciones = serializers.CharField()

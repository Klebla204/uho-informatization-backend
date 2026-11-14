from rest_framework import serializers


class ApproveLoanSerializer(serializers.Serializer):
    fecha_recogida_limite = serializers.DateTimeField(required=False, allow_null=True)


class RejectLoanSerializer(serializers.Serializer):
    motivo = serializers.CharField(required=True, allow_blank=False)


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

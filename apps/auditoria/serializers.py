from rest_framework import serializers

from .models import LogsAuditoria


class AuditLogSerializer(serializers.ModelSerializer):
    usuario_auth_uid = serializers.CharField(source="usuario.auth_uid", read_only=True, allow_null=True)

    class Meta:
        model = LogsAuditoria
        fields = (
            "id",
            "usuario",
            "usuario_auth_uid",
            "accion",
            "entidad",
            "entidad_id",
            "ip",
            "user_agent",
            "timestamp",
            "datos_anteriores",
            "datos_nuevos",
        )
        read_only_fields = fields

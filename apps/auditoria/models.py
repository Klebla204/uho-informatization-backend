import uuid

from django.conf import settings
from django.db import models


class LogsAuditoria(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="logs_auditoria",
    )
    accion = models.CharField(max_length=100)
    entidad = models.CharField(max_length=200)
    entidad_id = models.CharField(max_length=100, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    datos_anteriores = models.JSONField(null=True, blank=True)
    datos_nuevos = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "logs_auditoria"
        ordering = ("-timestamp",)
        indexes = [
            models.Index(fields=["usuario", "timestamp"]),
            models.Index(fields=["entidad", "entidad_id"]),
        ]

    def __str__(self):
        return f"{self.accion} - {self.entidad}"

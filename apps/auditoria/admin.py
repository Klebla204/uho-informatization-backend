from django.contrib import admin

from .models import LogsAuditoria


@admin.register(LogsAuditoria)
class LogsAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "usuario", "accion", "entidad", "ip")
    list_filter = ("accion", "entidad", "timestamp")
    search_fields = ("entidad", "entidad_id", "user_agent")
    readonly_fields = (
        "id",
        "usuario",
        "accion",
        "entidad",
        "entidad_id",
        "ip",
        "user_agent",
        "timestamp",
        "datos_anteriores",
        "datos_nuevos",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

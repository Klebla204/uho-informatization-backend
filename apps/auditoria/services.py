from .models import LogsAuditoria


def record_audit_event(*, request, action, entity, entity_id="", old_data=None, new_data=None, user=None):
    actor = user if user is not None else getattr(request, "user", None)
    if not actor or not actor.is_authenticated:
        actor = None
    return LogsAuditoria.objects.create(
        usuario=actor,
        accion=action,
        entidad=entity,
        entidad_id=str(entity_id or ""),
        ip=_get_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
        datos_anteriores=old_data,
        datos_nuevos=new_data,
    )


def _get_client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")

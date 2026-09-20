import json

from .models import LogsAuditoria


class AuditLogMiddleware:
    EXCLUDED_PATHS = ("/api/schema/", "/api/docs/", "/static/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.path.startswith(self.EXCLUDED_PATHS):
            return response

        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            user = None

        body = None
        if request.body:
            try:
                body = json.loads(request.body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                body = None

        LogsAuditoria.objects.create(
            usuario=user,
            accion=f"{request.method} {response.status_code}",
            entidad=request.resolver_match.view_name if request.resolver_match else request.path,
            entidad_id=request.resolver_match.kwargs.get("pk", "") if request.resolver_match else "",
            ip=self._get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            datos_nuevos=body,
        )
        return response

    @staticmethod
    def _get_client_ip(request):
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")

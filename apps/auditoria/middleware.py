import json

from .models import LogsAuditoria


class AuditLogMiddleware:
    EXCLUDED_PATHS = ("/api/schema/", "/api/docs/", "/api/token/", "/auth/login/", "/static/")
    SENSITIVE_KEYS = {"ci", "telefono", "phone", "password", "token", "access", "refresh", "secret", "authorization"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        excluded = request.path.startswith(self.EXCLUDED_PATHS)
        body = None if excluded else self._parse_json_body(request)
        response = self.get_response(request)

        if excluded:
            return response

        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            user = None

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
    def _parse_json_body(request):
        try:
            if request.body:
                return AuditLogMiddleware._redact_sensitive(json.loads(request.body.decode("utf-8")))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return None

    @staticmethod
    def _redact_sensitive(data):
        if isinstance(data, dict):
            return {
                key: "[REDACTADO]" if key.lower() in AuditLogMiddleware.SENSITIVE_KEYS else AuditLogMiddleware._redact_sensitive(value)
                for key, value in data.items()
            }
        if isinstance(data, list):
            return [AuditLogMiddleware._redact_sensitive(value) for value in data]
        return data

    @staticmethod
    def _get_client_ip(request):
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")

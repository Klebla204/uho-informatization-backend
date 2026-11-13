import json
import logging

from django.urls import resolve

from .services import record_audit_event

logger = logging.getLogger(__name__)


class AuditLogMiddleware:
    EXCLUDED_PATHS = ("/api/schema/", "/api/docs/", "/api/token/", "/static/")
    ACTIONS = {
        ("POST", "loan_request"): "LOAN_REQUESTED",
        ("POST", "counter_loan"): "LOAN_CREATED_IN_PERSON",
        ("POST", "loan_approve"): "LOAN_APPROVED",
        ("POST", "loan_reject"): "LOAN_REJECTED",
        ("POST", "loan_ready"): "LOAN_MARKED_READY",
        ("POST", "loan_collect"): "LOAN_COLLECTED",
        ("POST", "loan_return"): "LOAN_RETURNED",
        ("POST", "catalogo-importar"): "CATALOG_IMPORTED",
        ("GET", "reports-summary"): "REPORTS_ACCESSED",
        ("GET", "reports-export"): "REPORTS_EXPORTED",
    }
    SENSITIVE_KEYS = {"ci", "telefono", "phone", "password", "token", "access", "refresh", "secret", "authorization"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        excluded = request.path.startswith(self.EXCLUDED_PATHS)
        body = None if excluded else self._parse_json_body(request)
        previous_loan_state = self._loan_state(request) if not excluded else None
        response = self.get_response(request)

        if excluded:
            return response

        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            user = None

        match = request.resolver_match
        if match is None:
            try:
                match = resolve(request.path_info)
            except Exception:
                match = None
        view_name = match.view_name if match else request.path
        action = self.ACTIONS.get((request.method, view_name), f"{request.method} {response.status_code}")
        if response.status_code >= 400 and action in self.ACTIONS.values():
            action = f"{action}_FAILED"
        old_data = {"estado": previous_loan_state} if previous_loan_state else None
        new_data = body
        loan_id = match.kwargs.get("loan_id") if match else None
        current_loan_state = self._loan_state(request, loan_id=loan_id) if loan_id and response.status_code < 400 else None
        if current_loan_state:
            new_data = {"estado": current_loan_state}
        if view_name == "catalogo-importar" and response.status_code < 400:
            try:
                new_data = json.loads(response.content.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
                pass
        try:
            record_audit_event(
                request=request,
                user=user,
                action=action,
                entity=view_name,
                entity_id=(loan_id or (match.kwargs.get("pk", "") if match else "")),
                old_data=old_data,
                new_data=new_data,
            )
        except Exception:
            logger.exception("No se pudo guardar el registro de auditoría")
        return response

    @staticmethod
    def _loan_state(request, loan_id=None):
        match = request.resolver_match
        if match is None:
            try:
                match = resolve(request.path_info)
            except Exception:
                match = None
        if not loan_id and match:
            loan_id = match.kwargs.get("loan_id")
        if not loan_id:
            return None
        try:
            from apps.prestamos.models import Prestamo

            return Prestamo.objects.filter(pk=loan_id).values_list("estado", flat=True).first()
        except Exception:
            return None

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


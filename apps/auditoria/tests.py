from django.test import TestCase
from rest_framework.test import APIClient

from apps.users.models import CustomUser

from .models import LogsAuditoria


class AuditLogTests(TestCase):
    def test_authenticated_request_creates_immutable_audit_record_data(self):
        user = CustomUser.objects.create_user(
            auth_uid="audit-user",
            email="audit@example.com",
            nombre="Audit",
            apellidos="User",
            ci="01020304070",
            tipo_usuario="ESTUDIANTE",
        )
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get("/api/example/health/")

        self.assertEqual(response.status_code, 200)
        log = LogsAuditoria.objects.get()
        self.assertEqual(log.usuario, user)
        self.assertEqual(log.accion, "GET 200")
        self.assertEqual(log.entidad, "health_check")

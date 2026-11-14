from django.test import TestCase
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.rbac.models import Permission, Role, RolePermission, UserRole
from apps.users.models import CustomUser
from apps.catalogo.models import Biblioteca

from .models import LogsAuditoria


class AuditLogTests(TestCase):
    def create_scoped_admin(self, auth_uid, email, ci):
        admin = CustomUser.objects.create_user(
            auth_uid=auth_uid,
            email=email,
            nombre="Audit",
            apellidos="Admin",
            ci=ci,
            tipo_usuario="ADMINISTRADOR",
        )
        library = Biblioteca.objects.create(
            nombre=f"Biblioteca {auth_uid}",
            direccion="Calle 1",
            responsable=admin,
        )
        admin.biblioteca = library
        admin.save(update_fields=["biblioteca"])
        return admin, library

    def assign_scoped_role(self, admin, library, role):
        UserRole.objects.create(
            user=admin,
            role=role,
            resource_type="biblioteca",
            resource_id=str(library.id),
        )

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

    def test_login_success_and_failure_are_audited_without_credentials(self):
        user = CustomUser.objects.create_user(
            auth_uid="audit-login",
            email="audit-login@example.com",
            nombre="Audit",
            apellidos="Login",
            ci="01020304071",
        )
        user.tipo_usuario = "TRABAJADOR"
        user.set_password("correct-password")
        user.save()
        client = APIClient()

        failed = client.post("/auth/login/", {"username": "missing", "password": "do-not-store"}, format="json")
        succeeded = client.post("/auth/login/", {"username": "audit-login", "password": "correct-password"}, format="json")

        self.assertEqual(failed.status_code, 401)
        self.assertEqual(succeeded.status_code, 200)
        logs = list(LogsAuditoria.objects.filter(entidad="login").order_by("accion"))
        self.assertEqual({log.accion for log in logs}, {"LOGIN", "LOGIN_FAILED"})
        self.assertTrue(all("password" not in str(log.datos_nuevos or {}) for log in logs))

    def test_semantic_loan_action_is_audited_and_sensitive_values_redacted(self):
        user = CustomUser.objects.create_user(
            auth_uid="audit-loan-user",
            email="audit-loan@example.com",
            nombre="Audit",
            apellidos="Loan",
            ci="01020304072",
            tipo_usuario="ESTUDIANTE",
        )
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.post(
            "/api/v1/prestamos/solicitar/",
            {"libro": "00000000-0000-0000-0000-000000000001", "password": "hidden"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        log = LogsAuditoria.objects.get(entidad="loan_request")
        self.assertEqual(log.accion, "LOAN_REQUESTED_FAILED")
        self.assertEqual(log.datos_nuevos["password"], "[REDACTADO]")

    def test_admin_can_filter_logs_but_regular_user_cannot_query_them(self):
        call_command("seed_roles", verbosity=0)
        admin, library = self.create_scoped_admin(
            "audit-admin", "audit-admin@example.com", "01020304073"
        )
        regular = CustomUser.objects.create_user(
            auth_uid="audit-regular",
            email="audit-regular@example.com",
            nombre="Audit",
            apellidos="Regular",
            ci="01020304074",
            tipo_usuario="ESTUDIANTE",
        )
        LogsAuditoria.objects.create(usuario=admin, accion="CATALOG_IMPORTED", entidad="collection-import")
        LogsAuditoria.objects.create(usuario=admin, accion="REPORTS_ACCESSED", entidad="reports-summary")
        call_command("seed_roles", verbosity=0)
        admin_role = Role.objects.get(name="administrador_biblioteca")
        self.assign_scoped_role(admin, library, admin_role)
        client = APIClient()
        client.force_authenticate(user=admin)

        response = client.get("/api/v1/admin/auditoria/", {"accion": "IMPORTED"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["accion"], "CATALOG_IMPORTED")
        client.force_authenticate(user=regular)
        self.assertEqual(client.get("/api/v1/admin/auditoria/").status_code, 403)

    def test_audit_query_rejects_invalid_date_filter(self):
        admin, library = self.create_scoped_admin(
            "audit-date-admin", "audit-date-admin@example.com", "01020304075"
        )
        call_command("seed_roles", verbosity=0)
        admin_role = Role.objects.get(name="administrador_biblioteca")
        self.assign_scoped_role(admin, library, admin_role)
        client = APIClient()
        client.force_authenticate(user=admin)

        response = client.get("/api/v1/admin/auditoria/", {"desde": "not-a-date"})

        self.assertEqual(response.status_code, 400)

    def test_catalog_import_and_report_access_use_semantic_audit_actions(self):
        user, library = self.create_scoped_admin(
            "audit-semantic-admin", "audit-semantic-admin@example.com", "01020304076"
        )
        call_command("seed_roles", verbosity=0)
        self.assign_scoped_role(user, library, Role.objects.get(name="administrador_biblioteca"))
        self.assign_scoped_role(user, library, Role.objects.get(name="bibliotecario"))
        client = APIClient()
        client.force_authenticate(user=user)

        report_response = client.get("/api/v1/reportes/")
        client.post("/api/v1/admin/catalogo/importar/", {}, format="multipart")

        self.assertEqual(report_response.status_code, 200)
        self.assertTrue(LogsAuditoria.objects.filter(accion="REPORTS_ACCESSED", entidad="reports-summary").exists())
        self.assertTrue(LogsAuditoria.objects.filter(accion="CATALOG_IMPORTED_FAILED", entidad="catalogo-importar").exists())

    def test_catalog_create_action_is_audited_semantically(self):
        from apps.catalogo.models import Autor

        user = CustomUser.objects.create_user(
            auth_uid="audit-catalog-admin",
            email="audit-catalog-admin@example.com",
            nombre="Audit",
            apellidos="Catalog",
            ci="01020304077",
            tipo_usuario="BIBLIOTECARIO",
        )
        library = Biblioteca.objects.create(
            nombre="Biblioteca auditoría catálogo",
            direccion="Calle 1",
            responsable=user,
        )
        user.biblioteca = library
        user.save(update_fields=["biblioteca"])
        call_command("seed_roles", verbosity=0)
        role = Role.objects.get(name="bibliotecario")
        self.assign_scoped_role(user, library, role)
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.post(
            "/api/v1/admin/catalogo/autores/",
            {"nombre": "Ada", "apellidos": "Lovelace"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(Autor.objects.filter(nombre="Ada").exists())
        self.assertTrue(LogsAuditoria.objects.filter(accion="POST 201", entidad="admin-autor-list").exists())

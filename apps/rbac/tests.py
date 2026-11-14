from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from apps.catalogo.models import Biblioteca
from apps.users.models import CustomUser

from .models import Permission, Role, RolePermission, UserRole


class RBACAdminApiTests(TestCase):
    def setUp(self):
        call_command("seed_roles", verbosity=0)
        self.client = APIClient()
        self.admin = CustomUser.objects.create_user(
            auth_uid="rbac-super-admin",
            email="rbac-super-admin@example.com",
            nombre="Super",
            apellidos="Admin",
            ci="RBAC-TEST-ADMIN",
            tipo_usuario="SUPER_ADMIN",
        )
        self.super_role = Role.objects.get(name="super_admin")
        UserRole.objects.create(user=self.admin, role=self.super_role)
        self.client.force_authenticate(user=self.admin)

    def test_seed_contains_all_predefined_roles(self):
        self.assertEqual(
            set(Role.objects.filter(is_system=True).values_list("name", flat=True)),
            {
                "visitante", "estudiante", "trabajador", "bibliotecario",
                "administrador_biblioteca", "super_admin",
            },
        )

    def test_audit_permission_is_available_and_granted_to_admin_roles(self):
        response = self.client.get("/api/v1/admin/rbac/permisos/")

        self.assertEqual(response.status_code, 200)
        audit_permission = Permission.objects.get(name="auditoria.view")
        listed_permissions = response.json()["results"]
        self.assertTrue(any(item["name"] == "auditoria.view" for item in listed_permissions))
        for role_name in ("administrador_biblioteca", "super_admin"):
            role = Role.objects.get(name=role_name)
            self.assertTrue(RolePermission.objects.filter(
                role=role,
                permission=audit_permission,
                allow=True,
            ).exists())

    def test_super_admin_can_create_role_with_module_permissions(self):
        permission = Permission.objects.get(name="catalogo.view")

        response = self.client.post(
            "/api/v1/admin/rbac/roles/",
            {
                "name": "apoyo_catalogo",
                "display_name": "Apoyo de Catálogo",
                "description": "Acceso de lectura al catálogo.",
                "permissions": [permission.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        role = Role.objects.get(name="apoyo_catalogo")
        self.assertTrue(RolePermission.objects.filter(role=role, permission=permission, allow=True).exists())
        self.assertEqual(response.json()["permission_details"][0]["module"], "catalogo")

    def test_super_admin_can_replace_permissions_on_custom_role(self):
        role = Role.objects.create(name="editable_role", display_name="Editable")
        catalog_permission = Permission.objects.get(name="catalogo.view")
        loan_permission = Permission.objects.get(name="prestamos.request")
        RolePermission.objects.create(role=role, permission=catalog_permission)

        response = self.client.patch(
            f"/api/v1/admin/rbac/roles/{role.id}/",
            {"permissions": [loan_permission.id]},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(RolePermission.objects.filter(role=role, permission=catalog_permission).exists())
        self.assertTrue(RolePermission.objects.filter(role=role, permission=loan_permission, allow=True).exists())

    def test_super_admin_can_assign_role_to_user(self):
        user = CustomUser.objects.create_user(
            auth_uid="rbac-student",
            email="rbac-student@example.com",
            nombre="User",
            apellidos="Student",
            ci="RBAC-TEST-USER",
            tipo_usuario="ESTUDIANTE",
        )
        role = Role.objects.get(name="estudiante")

        response = self.client.post(
            "/api/v1/admin/rbac/asignaciones/",
            {"user": str(user.id), "role": role.id},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        assignment = UserRole.objects.get(user=user, role=role)
        self.assertEqual(assignment.assigned_by, self.admin)

    def test_assigning_a_role_replaces_the_users_previous_role(self):
        user = CustomUser.objects.create_user(
            auth_uid="rbac-single-role-user",
            email="rbac-single-role@example.com",
            nombre="Single",
            apellidos="Role",
            ci="RBAC-SINGLE-ROLE",
            tipo_usuario="ESTUDIANTE",
        )
        student_role = Role.objects.get(name="estudiante")
        worker_role = Role.objects.get(name="trabajador")
        UserRole.objects.create(user=user, role=student_role, assigned_by=self.admin)

        response = self.client.post(
            "/api/v1/admin/rbac/asignaciones/",
            {"user": str(user.id), "role": worker_role.id},
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.json())
        self.assertEqual(list(UserRole.objects.filter(user=user).values_list("role__name", flat=True)), ["trabajador"])

    def test_super_admin_cannot_receive_another_role(self):
        response = self.client.post(
            "/api/v1/admin/rbac/asignaciones/",
            {"user": str(self.admin.id), "role": Role.objects.get(name="trabajador").id},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(list(UserRole.objects.filter(user=self.admin).values_list("role__name", flat=True)), ["super_admin"])

    def test_super_admin_can_promote_student_to_librarian(self):
        student = CustomUser.objects.create_user(
            auth_uid="rbac-student-librarian",
            email="rbac-student-librarian@example.com",
            nombre="Part-time",
            apellidos="Librarian",
            ci="RBAC-TEST-STUDENT-LIBRARIAN",
            tipo_usuario="ESTUDIANTE",
        )
        student_role = Role.objects.get(name="estudiante")
        librarian_role = Role.objects.get(name="bibliotecario")
        UserRole.objects.create(user=student, role=student_role, assigned_by=self.admin)

        response = self.client.post(
            "/api/v1/admin/rbac/asignaciones/",
            {"user": str(student.id), "role": librarian_role.id},
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.json())
        student.refresh_from_db()
        self.assertEqual(student.tipo_usuario, "BIBLIOTECARIO")
        self.assertTrue(UserRole.objects.filter(user=student, role=librarian_role).exists())
        self.assertFalse(UserRole.objects.filter(user=student, role=student_role).exists())

    def test_super_admin_can_change_staff_between_librarian_and_administrator(self):
        library = Biblioteca.objects.create(
            nombre="Sede de cambio de rol",
            direccion="Por definir",
            responsable=self.admin,
        )
        librarian = CustomUser.objects.create_user(
            auth_uid="rbac-role-change",
            email="rbac-role-change@example.com",
            nombre="Role",
            apellidos="Change",
            ci="RBAC-ROLE-CHANGE",
            tipo_usuario="BIBLIOTECARIO",
            biblioteca=library,
        )
        librarian_role = Role.objects.get(name="bibliotecario")
        administrator_role = Role.objects.get(name="administrador_biblioteca")
        UserRole.objects.create(
            user=librarian,
            role=librarian_role,
            resource_type="biblioteca",
            resource_id=str(library.id),
            assigned_by=self.admin,
        )

        promoted = self.client.post(
            "/api/v1/admin/rbac/asignaciones/",
            {"user": str(librarian.id), "role": administrator_role.id},
            format="json",
        )

        self.assertEqual(promoted.status_code, 201, promoted.json())
        librarian.refresh_from_db()
        self.assertEqual(librarian.tipo_usuario, "ADMINISTRADOR")
        self.assertEqual(librarian.biblioteca, library)
        self.assertFalse(UserRole.objects.filter(user=librarian, role=librarian_role).exists())
        self.assertEqual(promoted.json()["resource_id"], str(library.id))

        returned = self.client.post(
            "/api/v1/admin/rbac/asignaciones/",
            {"user": str(librarian.id), "role": librarian_role.id},
            format="json",
        )

        self.assertEqual(returned.status_code, 201, returned.json())
        librarian.refresh_from_db()
        self.assertEqual(librarian.tipo_usuario, "BIBLIOTECARIO")
        self.assertEqual(librarian.biblioteca, library)
        self.assertFalse(UserRole.objects.filter(user=librarian, role=administrator_role).exists())

    def test_super_admin_can_return_librarian_to_student(self):
        library = Biblioteca.objects.create(
            nombre="Sede de retorno",
            direccion="Por definir",
            responsable=self.admin,
        )
        librarian = CustomUser.objects.create_user(
            auth_uid="rbac-librarian-student",
            email="rbac-librarian-student@example.com",
            nombre="Return",
            apellidos="Student",
            ci="RBAC-LIBRARIAN-STUDENT",
            tipo_usuario="BIBLIOTECARIO",
            biblioteca=library,
        )
        librarian_role = Role.objects.get(name="bibliotecario")
        student_role = Role.objects.get(name="estudiante")
        UserRole.objects.create(
            user=librarian,
            role=librarian_role,
            resource_type="biblioteca",
            resource_id=str(library.id),
            assigned_by=self.admin,
        )
        UserRole.objects.create(user=librarian, role=student_role, assigned_by=self.admin)

        response = self.client.post(
            "/api/v1/admin/rbac/asignaciones/",
            {"user": str(librarian.id), "role": student_role.id},
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.json())
        librarian.refresh_from_db()
        self.assertEqual(librarian.tipo_usuario, "ESTUDIANTE")
        self.assertIsNone(librarian.biblioteca)
        self.assertTrue(UserRole.objects.filter(user=librarian, role=student_role).exists())
        self.assertFalse(UserRole.objects.filter(user=librarian, role=librarian_role).exists())

    def test_student_cannot_be_changed_directly_to_administrator(self):
        student = CustomUser.objects.create_user(
            auth_uid="rbac-student-no-admin",
            email="rbac-student-no-admin@example.com",
            nombre="Student",
            apellidos="No Admin",
            ci="RBAC-STUDENT-NO-ADMIN",
            tipo_usuario="ESTUDIANTE",
        )
        administrator_role = Role.objects.get(name="administrador_biblioteca")

        response = self.client.post(
            "/api/v1/admin/rbac/asignaciones/",
            {"user": str(student.id), "role": administrator_role.id},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        student.refresh_from_db()
        self.assertEqual(student.tipo_usuario, "ESTUDIANTE")
        self.assertFalse(UserRole.objects.filter(user=student, role=administrator_role).exists())

    def test_staff_roles_can_be_assigned_without_library_then_scoped_later(self):
        librarian = CustomUser.objects.create_user(
            auth_uid="rbac-scoped-librarian",
            email="rbac-scoped-librarian@example.com",
            nombre="Library",
            apellidos="Staff",
            ci="RBAC-SCOPED-LIBRARIAN",
            tipo_usuario="BIBLIOTECARIO",
        )
        library = Biblioteca.objects.create(
            nombre="Sede de prueba",
            direccion="Por definir",
            responsable=self.admin,
        )
        role = Role.objects.get(name="bibliotecario")

        unscoped = self.client.post(
            "/api/v1/admin/rbac/asignaciones/",
            {"user": str(librarian.id), "role": role.id},
            format="json",
        )
        self.assertEqual(unscoped.status_code, 201)
        librarian.refresh_from_db()
        self.assertIsNone(librarian.biblioteca)
        self.assertIsNone(unscoped.json()["resource_type"])
        self.assertIsNone(unscoped.json()["resource_id"])

        self.client.delete(f"/api/v1/admin/rbac/asignaciones/{unscoped.json()['id']}/")
        assigned = self.client.post(
            "/api/v1/admin/rbac/asignaciones/",
            {"user": str(librarian.id), "role": role.id, "biblioteca": str(library.id)},
            format="json",
        )

        self.assertEqual(assigned.status_code, 201)
        librarian.refresh_from_db()
        self.assertEqual(librarian.biblioteca, library)
        self.assertEqual(assigned.json()["resource_type"], "biblioteca")
        self.assertEqual(assigned.json()["resource_id"], str(library.id))
        self.assertFalse(UserRole.objects.filter(
            user=librarian,
            role=role,
            resource_type__isnull=True,
            resource_id__isnull=True,
        ).exists())

        new_library = Biblioteca.objects.create(
            nombre="Nueva sede de prueba",
            direccion="Por definir",
            responsable=self.admin,
        )
        transferred = self.client.post(
            "/api/v1/admin/rbac/asignaciones/",
            {"user": str(librarian.id), "role": role.id, "biblioteca": str(new_library.id)},
            format="json",
        )

        self.assertEqual(transferred.status_code, 201)
        librarian.refresh_from_db()
        self.assertEqual(librarian.biblioteca, new_library)
        self.assertFalse(UserRole.objects.filter(
            user=librarian,
            resource_type="biblioteca",
            resource_id=str(library.id),
        ).exists())
        self.assertTrue(UserRole.objects.filter(
            user=librarian,
            resource_type="biblioteca",
            resource_id=str(new_library.id),
        ).exists())

        administrator = CustomUser.objects.create_user(
            auth_uid="rbac-scoped-administrator",
            email="rbac-scoped-administrator@example.com",
            nombre="Library",
            apellidos="Administrator",
            ci="RBAC-SCOPED-ADMINISTRATOR",
            tipo_usuario="ADMINISTRADOR",
        )
        administrator_role = Role.objects.get(name="administrador_biblioteca")
        unscoped_admin = self.client.post(
            "/api/v1/admin/rbac/asignaciones/",
            {"user": str(administrator.id), "role": administrator_role.id},
            format="json",
        )
        self.assertEqual(unscoped_admin.status_code, 201)
        assigned_admin = self.client.post(
            "/api/v1/admin/rbac/asignaciones/",
            {"user": str(administrator.id), "role": administrator_role.id, "biblioteca": str(library.id)},
            format="json",
        )
        self.assertEqual(assigned_admin.status_code, 201)
        administrator.refresh_from_db()
        self.assertEqual(administrator.biblioteca, library)

    def test_user_directory_can_filter_staff_type_for_multilibrary_panel(self):
        CustomUser.objects.create_user(
            auth_uid="rbac-directory-librarian",
            email="rbac-directory-librarian@example.com",
            nombre="Library",
            apellidos="Staff",
            ci="RBAC-DIRECTORY-LIBRARIAN",
            tipo_usuario="BIBLIOTECARIO",
        )
        CustomUser.objects.create_user(
            auth_uid="rbac-directory-admin",
            email="rbac-directory-admin@example.com",
            nombre="Library",
            apellidos="Admin",
            ci="RBAC-DIRECTORY-ADMIN",
            tipo_usuario="ADMINISTRADOR",
        )

        response = self.client.get(
            "/api/v1/admin/rbac/usuarios/?tipo_usuario=BIBLIOTECARIO"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [user["auth_uid"] for user in response.json()],
            ["rbac-directory-librarian"],
        )

    def test_non_super_admin_cannot_manage_roles(self):
        regular_user = CustomUser.objects.create_user(
            auth_uid="rbac-regular-user",
            email="rbac-regular@example.com",
            nombre="Regular",
            apellidos="User",
            ci="RBAC-TEST-REGULAR",
            tipo_usuario="ADMINISTRADOR",
        )
        regular_role = Role.objects.create(name="regular_admin")
        manage_permission = Permission.objects.get(name="admin.manage")
        RolePermission.objects.create(role=regular_role, permission=manage_permission)
        UserRole.objects.create(user=regular_user, role=regular_role)
        self.client.force_authenticate(user=regular_user)

        response = self.client.get("/api/v1/admin/rbac/roles/")

        self.assertEqual(response.status_code, 403)

    def test_predefined_role_cannot_be_deleted(self):
        response = self.client.delete(f"/api/v1/admin/rbac/roles/{self.super_role.id}/")

        self.assertEqual(response.status_code, 400)
        self.assertTrue(Role.objects.filter(pk=self.super_role.pk).exists())

    def test_super_admin_role_cannot_lose_management_permission(self):
        response = self.client.patch(
            f"/api/v1/admin/rbac/roles/{self.super_role.id}/",
            {"permissions": [Permission.objects.get(name="catalogo.view").id]},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue(RolePermission.objects.filter(
            role=self.super_role,
            permission__name="admin.manage",
            allow=True,
        ).exists())

    def test_expired_super_admin_assignment_cannot_access_api(self):
        from django.utils import timezone
        from datetime import timedelta

        UserRole.objects.filter(user=self.admin, role=self.super_role).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )

        response = self.client.get("/api/v1/admin/rbac/roles/")

        self.assertEqual(response.status_code, 403)
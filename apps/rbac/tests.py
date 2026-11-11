from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

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
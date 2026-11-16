from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.rbac.models import Role, UserRole
from apps.users.models import CustomUser

from .models import Carrera, Facultad


class AcademicModelTests(TestCase):
	def test_carrera_belongs_to_facultad_and_supports_soft_delete(self):
		facultad = Facultad.objects.create(nombre="Ingenieria", codigo="ING", decano="Decano")
		carrera = Carrera.objects.create(nombre="Informatica", codigo="INF", facultad=facultad)

		self.assertIsNotNone(facultad.id)
		self.assertEqual(carrera.facultad, facultad)
		self.assertTrue(carrera.activa)


class NomenclatureAdminApiTests(APITestCase):
	def setUp(self):
		call_command("seed_roles", verbosity=0)
		self.admin = CustomUser.objects.create_user(
			auth_uid="nomenclature-super-admin",
			email="nomenclature-admin@example.com",
			nombre="Admin",
			apellidos="UHO",
			ci="NOMENCLATURE-ADMIN",
			tipo_usuario="SUPER_ADMIN",
		)
		UserRole.objects.create(user=self.admin, role=Role.objects.get(name="super_admin"))
		self.client.force_authenticate(user=self.admin)

	def test_super_admin_can_create_faculty_career_and_cargo(self):
		faculty_response = self.client.post(
			reverse("admin-facultad-list"),
			{"nombre": "Facultad de prueba", "codigo": "FTEST", "decano": "Decana"},
			format="json",
		)
		self.assertEqual(faculty_response.status_code, 201, faculty_response.data)

		career_response = self.client.post(
			reverse("admin-carrera-list"),
			{"nombre": "Carrera de prueba", "codigo": "CTEST", "facultad": faculty_response.data["id"]},
			format="json",
		)
		self.assertEqual(career_response.status_code, 201, career_response.data)
		self.assertEqual(career_response.data["facultad_nombre"], "Facultad de prueba")

		cargo_response = self.client.post(
			reverse("admin-cargo-list"),
			{"nombre": "Cargo de prueba", "nivel": "Superior"},
			format="json",
		)
		self.assertEqual(cargo_response.status_code, 201, cargo_response.data)

	def test_delete_nomenclature_item_is_soft_delete(self):
		response = self.client.post(
			reverse("admin-facultad-list"),
			{"nombre": "Facultad inactiva", "codigo": "FINACT"},
			format="json",
		)
		delete_response = self.client.delete(reverse("admin-facultad-detail", kwargs={"pk": response.data["id"]}))

		self.assertEqual(delete_response.status_code, 204)
		self.assertFalse(Facultad.objects.get(pk=response.data["id"]).activa)

	def test_user_without_admin_manage_cannot_manage_nomenclatures(self):
		self.admin.user_roles.all().delete()
		self.admin.tipo_usuario = "ESTUDIANTE"
		self.admin.save(update_fields=["tipo_usuario"])

		response = self.client.get(reverse("admin-facultad-list"))

		self.assertEqual(response.status_code, 403)

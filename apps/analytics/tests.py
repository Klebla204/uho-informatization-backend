from datetime import timedelta
from io import BytesIO

from django.test import TestCase
from django.utils import timezone
from openpyxl import load_workbook
from rest_framework.test import APIClient

from apps.catalogo.models import Biblioteca, Categoria, Editorial, Ejemplar, Libro
from apps.prestamos.models import Prestamo
from apps.rbac.models import Permission, Role, RolePermission, UserRole
from apps.users.models import CustomUser


class ReportsApiTests(TestCase):
	def setUp(self):
		self.client = APIClient()
		self.user = CustomUser.objects.create_user(
			auth_uid="reports-user",
			email="reports-user@example.com",
			nombre="Ada",
			apellidos="Lovelace",
			ci="REPORTS-USER-1",
			tipo_usuario="ADMINISTRADOR",
		)
		self.librarian = CustomUser.objects.create_user(
			auth_uid="reports-librarian",
			email="reports-librarian@example.com",
			nombre="Grace",
			apellidos="Hopper",
			ci="REPORTS-LIBRARIAN-1",
			tipo_usuario="BIBLIOTECARIO",
		)
		self.role = Role.objects.create(name="reports_admin")
		permission = Permission.objects.create(name="reportes.view")
		RolePermission.objects.create(role=self.role, permission=permission)
		self.library = Biblioteca.objects.create(
			nombre="Central", direccion="Calle 1", responsable=self.librarian
		)
		self.user.biblioteca = self.library
		self.user.save(update_fields=["biblioteca"])
		UserRole.objects.create(
			user=self.user,
			role=self.role,
			resource_type="biblioteca",
			resource_id=str(self.library.id),
		)
		other_library = Biblioteca.objects.create(
			nombre="Tecnica", direccion="Calle 2", responsable=self.librarian
		)
		publisher = Editorial.objects.create(nombre="Editorial UHO")
		category = Categoria.objects.create(nombre="Ciencia")
		self.book = Libro.objects.create(titulo="Analisis", editorial=publisher)
		self.book.categorias.add(category)
		self.copy = Ejemplar.objects.create(
			libro=self.book, biblioteca=self.library, codigo_ejemplar="REPORT-001"
		)
		other_copy = Ejemplar.objects.create(
			libro=self.book, biblioteca=other_library, codigo_ejemplar="REPORT-002"
		)
		self.loan = Prestamo.objects.create(
			usuario=self.user,
			ejemplar=self.copy,
			biblioteca=self.library,
			fecha_devolucion_pactada=timezone.now() + timedelta(days=7),
			estado="DEVUELTO",
		)
		Prestamo.objects.filter(pk=self.loan.pk).update(estado="DEVUELTO")
		Prestamo.objects.create(
			usuario=self.user,
			ejemplar=other_copy,
			biblioteca=other_library,
			fecha_devolucion_pactada=timezone.now() - timedelta(days=2),
			estado="VENCIDO",
			fecha_devolucion_real=timezone.now() - timedelta(days=1),
		)
		self.client.force_authenticate(user=self.user)

	def test_summary_returns_real_reports_and_applies_library_filter(self):
		response = self.client.get(
			"/api/v1/reportes/",
			{"desde": timezone.localdate().isoformat(), "hasta": timezone.localdate().isoformat(), "biblioteca": str(self.library.id)},
		)

		self.assertEqual(response.status_code, 200)
		data = response.json()
		self.assertEqual(data["resumen"]["total_prestamos"], 1)
		self.assertEqual(data["resumen"]["devoluciones"], 1)
		self.assertEqual(data["resumen"]["vencidos"], 0)
		self.assertEqual(data["libros_mas_prestados"][0]["ejemplar__libro__titulo"], "Analisis")
		self.assertEqual(data["prestamos_por_periodo"][0]["periodo"], timezone.localdate().replace(day=1).isoformat())
		self.assertEqual(data["coleccion_por_categoria"][0]["nombre"], "Ciencia")

	def test_summary_requires_permission_and_valid_dates(self):
		response = self.client.get(
			"/api/v1/reportes/",
			{"desde": "no-es-fecha", "hasta": timezone.localdate().isoformat()},
		)
		self.assertEqual(response.status_code, 400)

		response = self.client.get(
			"/api/v1/reportes/",
			{
				"desde": timezone.localdate().isoformat(),
				"hasta": (timezone.localdate() - timedelta(days=1)).isoformat(),
			},
		)
		self.assertEqual(response.status_code, 400)

		RolePermission.objects.filter(role=self.role).delete()
		response = self.client.get("/api/v1/reportes/")
		self.assertEqual(response.status_code, 403)

		self.client.force_authenticate(user=None)
		response = self.client.get("/api/v1/reportes/")
		self.assertEqual(response.status_code, 401)

	def test_exports_return_valid_xlsx_and_pdf(self):
		xlsx_response = self.client.get("/api/v1/reportes/exportar/", {"formato": "xlsx"})
		pdf_response = self.client.get("/api/v1/reportes/exportar/", {"formato": "pdf"})

		self.assertEqual(xlsx_response.status_code, 200)
		workbook = load_workbook(BytesIO(xlsx_response.content), read_only=True)
		self.assertIn("Prestamos vencidos", workbook.sheetnames)
		self.assertEqual(pdf_response.status_code, 200)
		self.assertTrue(pdf_response.content.startswith(b"%PDF"))

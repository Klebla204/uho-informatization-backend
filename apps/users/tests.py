from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.academics.models import Carrera, Facultad

from .models import CustomUser


class CustomUserModelTests(TestCase):
	def test_user_matches_institutional_schema_and_encrypts_sensitive_data(self):
		user = CustomUser.objects.create_user(
			auth_uid="uho-123",
			email="ana@example.com",
			nombre="Ana",
			apellidos="Pérez",
			ci="01020304050",
			telefono="55512345",
			tipo_usuario="ESTUDIANTE",
		)

		user.refresh_from_db()

		self.assertIsNotNone(user.id)
		self.assertEqual(user.auth_uid, "uho-123")
		self.assertEqual(user.ci, "01020304050")
		self.assertEqual(user.telefono, "55512345")

		ci_field = CustomUser._meta.get_field("ci")
		stored_ci = ci_field.get_prep_value("01020304050")
		self.assertNotEqual(stored_ci, "01020304050")


class ProfileEndpointTests(TestCase):
	def setUp(self):
		self.user = CustomUser.objects.create_user(auth_uid='u1', email='u1@example.com', nombre='Ana', apellidos='Perez', ci='01020304050', tipo_usuario='ESTUDIANTE')
		self.faculty = Facultad.objects.create(nombre='Técnica', codigo='FT')
		self.career = Carrera.objects.create(nombre='Informática', codigo='INF', facultad=self.faculty)
		self.client = APIClient()
		self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(self.user).access_token))

	def _complete_profile(self):
		return self.client.patch('/api/v1/usuarios/mi-perfil/', {
			'telefono': '55512345', 'facultad': str(self.faculty.id), 'carrera': str(self.career.id),
			'anio': 3, 'tipo_curso': 'Diurno',
		}, format='json')

	def test_new_student_profile_is_incomplete_and_has_no_card(self):
		profile = self.client.get('/api/v1/usuarios/mi-perfil/').json()
		self.assertFalse(profile['perfil_completo'])
		self.assertEqual(self.client.get('/api/v1/usuarios/mi-carnet/').status_code, 409)
		self.assertEqual(self.client.get('/api/v1/usuarios/mi-carnet/pdf/').status_code, 409)

	def test_completing_profile_generates_card_with_user_id_qr(self):
		response = self._complete_profile()
		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.json()['perfil_completo'])
		card = self.client.get('/api/v1/usuarios/mi-carnet/').json()
		self.assertEqual(card['codigo_qr'], str(self.user.id))
		self.assertEqual(card['carrera'], 'Informática')
		self.assertIn('<svg', card['qr_svg'])
		self.assertEqual(self.user.carnet.codigo_qr, str(self.user.id))

	def test_card_pdf_is_generated(self):
		self._complete_profile()
		response = self.client.get('/api/v1/usuarios/mi-carnet/pdf/')
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response['Content-Type'], 'application/pdf')
		self.assertTrue(response.content.startswith(b'%PDF'))

	def test_career_must_belong_to_faculty(self):
		other = Facultad.objects.create(nombre='Sociales', codigo='FS')
		response = self.client.patch('/api/v1/usuarios/mi-perfil/', {
			'telefono': '55512345', 'facultad': str(other.id), 'carrera': str(self.career.id),
			'anio': 1, 'tipo_curso': 'Diurno',
		}, format='json')
		self.assertEqual(response.status_code, 400)

	def test_user_can_verify_name_and_ci(self):
		response = self.client.patch('/api/v1/usuarios/mi-perfil/', {'nombre': 'Ana María', 'ci': '99010112345'}, format='json')
		self.assertEqual(response.json()['nombre'], 'Ana María')
		self.assertEqual(response.json()['ci'], '99010112345')

	def test_card_requires_authentication(self):
		self.assertEqual(APIClient().get('/api/v1/usuarios/mi-carnet/').status_code, 401)

	def test_faculty_and_career_lists(self):
		faculties = self.client.get('/api/v1/usuarios/facultades/')
		careers = self.client.get('/api/v1/usuarios/carreras/', {'facultad': str(self.faculty.id)})
		self.assertEqual([f['nombre'] for f in faculties.json()], ['Técnica'])
		self.assertEqual([c['nombre'] for c in careers.json()], ['Informática'])

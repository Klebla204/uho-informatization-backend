from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

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
		self.client = APIClient()
		self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(self.user).access_token))

	def test_profile_masks_ci_and_updates_phone(self):
		response = self.client.get('/api/v1/usuarios/mi-perfil/')
		self.assertEqual(response.status_code, 200)
		self.assertNotIn('01020304050', response.content.decode())
		response = self.client.patch('/api/v1/usuarios/mi-perfil/', {'telefono': '55512345'}, format='json')
		self.assertEqual(response.json()['telefono'], '55512345')

	def test_card_requires_authentication(self):
		self.assertEqual(self.client.get('/api/v1/usuarios/mi-carnet/').json()['codigo_qr'], str(self.user.id))
		self.assertEqual(APIClient().get('/api/v1/usuarios/mi-carnet/').status_code, 401)

from django.test import TestCase

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

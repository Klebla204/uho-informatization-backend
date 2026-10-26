import os
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command, CommandError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

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


@override_settings(
	DEBUG=True,
	SECRET_KEY="temporary-test-signing-key-with-more-than-32-bytes",
	DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
)
class LocalDemoAuthTests(TestCase):
	def test_demo_commands_are_disabled_without_explicit_opt_in(self):
		with patch.dict(os.environ, {}, clear=True):
			with self.assertRaises(CommandError):
				call_command("crear_usuarios_demo", stdout=StringIO())

	def test_demo_user_can_get_token_but_real_user_cannot(self):
		with patch.dict(os.environ, {"ENABLE_LOCAL_DEMO_AUTH": "true"}):
			call_command("seed_roles", stdout=StringIO())
			call_command("crear_usuarios_demo", stdout=StringIO())
			token_output = StringIO()
			call_command("token_demo", "demo-estudiante", stdout=token_output)

		token_line = next(line for line in token_output.getvalue().splitlines() if line.startswith("Bearer "))
		access_token = token_line.removeprefix("Bearer ")
		self.assertEqual(str(AccessToken(access_token)["user_id"]), str(CustomUser.objects.get(auth_uid="demo-estudiante").id))

		client = APIClient()
		client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
		response = client.get("/api/v1/libros/")
		self.assertEqual(response.status_code, 200)

		real_user = CustomUser.objects.create_user(
			auth_uid="real-institution-user",
			email="real@example.com",
			nombre="Real",
			apellidos="User",
			ci="01020304999",
			tipo_usuario="ESTUDIANTE",
		)
		self.assertFalse(real_user.es_usuario_demo)
		with patch.dict(os.environ, {"ENABLE_LOCAL_DEMO_AUTH": "true"}):
			with self.assertRaises(CommandError):
				call_command("token_demo", real_user.auth_uid, stdout=StringIO())

	@override_settings(DEBUG=False)
	def test_demo_commands_remain_blocked_when_debug_is_off(self):
		with patch.dict(os.environ, {"ENABLE_LOCAL_DEMO_AUTH": "true"}):
			with self.assertRaises(CommandError):
				call_command("crear_usuarios_demo", stdout=StringIO())

	@override_settings(DATABASES={"default": {"ENGINE": "django.db.backends.postgresql", "NAME": "test"}})
	def test_demo_commands_remain_blocked_for_postgresql(self):
		with patch.dict(os.environ, {"ENABLE_LOCAL_DEMO_AUTH": "true"}):
			with self.assertRaises(CommandError):
				call_command("crear_usuarios_demo", stdout=StringIO())

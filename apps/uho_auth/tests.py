from unittest.mock import patch

from django.test import TestCase

from apps.users.models import CustomUser

UNIVERSITY_USER = {
    "username": "jperez",
    "name": "Juan",
    "surname": "Pérez",
    "national_id": "90010112345",
    "user_type": "estudiante",
    "active": True,
}


class LoginTests(TestCase):
    url = "/auth/login/"

    def test_local_user_logs_in_without_university_query(self):
        local = CustomUser.objects.create_user(
            auth_uid="local", email="local@example.com", nombre="L", apellidos="U",
            ci="01020304050", tipo_usuario="TRABAJADOR",
        )
        local.set_password("clave-segura-123")
        local.save()
        with patch("apps.uho_auth.views.uho_login") as uho:
            response = self.client.post(self.url, {"username": "local", "password": "clave-segura-123"}, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.json())
        uho.assert_not_called()

    def test_university_user_is_created_locally(self):
        with patch("apps.uho_auth.views.uho_login", return_value=UNIVERSITY_USER):
            response = self.client.post(self.url, {"username": "jperez", "password": "x"}, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        user = CustomUser.objects.get(auth_uid="jperez")
        self.assertEqual(user.ci, "90010112345")
        self.assertEqual(user.tipo_usuario, "ESTUDIANTE")

    def test_invalid_credentials_return_401(self):
        with patch("apps.uho_auth.views.uho_login", return_value=None):
            response = self.client.post(self.url, {"username": "x", "password": "y"}, content_type="application/json")
        self.assertEqual(response.status_code, 401)

    def test_inactive_university_account_is_rejected(self):
        with patch("apps.uho_auth.views.uho_login", return_value={**UNIVERSITY_USER, "active": False}):
            response = self.client.post(self.url, {"username": "jperez", "password": "x"}, content_type="application/json")
        self.assertEqual(response.status_code, 401)
        self.assertFalse(CustomUser.objects.filter(auth_uid="jperez").exists())

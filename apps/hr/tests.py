from django.test import TestCase

from apps.users.models import CustomUser

from .models import Cargo, PerfilTrabajador


class WorkerProfileTests(TestCase):
	def test_worker_profile_links_user_and_cargo(self):
		user = CustomUser.objects.create_user(
			auth_uid="worker-1",
			email="worker@example.com",
			nombre="Luis",
			apellidos="Garcia",
			ci="01020304051",
			tipo_usuario="TRABAJADOR",
		)
		cargo = Cargo.objects.create(nombre="Profesor", nivel="Superior")
		profile = PerfilTrabajador.objects.create(
			usuario=user,
			cargo=cargo,
			departamento="Informatica",
			tipo_contrato="Tiempo completo",
		)

		self.assertIsNotNone(profile.id)
		self.assertEqual(profile.usuario, user)
		self.assertEqual(profile.cargo, cargo)
		self.assertTrue(cargo.activa)

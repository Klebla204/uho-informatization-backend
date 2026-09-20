from django.test import TestCase

from apps.academics.models import Carrera, Facultad
from apps.users.models import CustomUser

from .models import PerfilEstudiante


class StudentProfileTests(TestCase):
	def test_student_profile_links_user_career_and_faculty(self):
		user = CustomUser.objects.create_user(
			auth_uid="student-1",
			email="student@example.com",
			nombre="Ana",
			apellidos="Perez",
			ci="01020304050",
			tipo_usuario="ESTUDIANTE",
		)
		faculty = Facultad.objects.create(nombre="Ingenieria", codigo="ING")
		career = Carrera.objects.create(nombre="Informatica", codigo="INF", facultad=faculty)
		profile = PerfilEstudiante.objects.create(
			usuario=user,
			carrera=career,
			facultad=faculty,
			anio=2,
			tipo_curso="Diurno",
			matricula="MAT-001",
		)

		self.assertIsNotNone(profile.id)
		self.assertEqual(profile.usuario, user)
		self.assertEqual(profile.carrera, career)
		self.assertEqual(profile.facultad, faculty)

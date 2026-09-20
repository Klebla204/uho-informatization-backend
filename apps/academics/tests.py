from django.test import TestCase

from .models import Carrera, Facultad


class AcademicModelTests(TestCase):
	def test_carrera_belongs_to_facultad_and_supports_soft_delete(self):
		facultad = Facultad.objects.create(nombre="Ingenieria", codigo="ING", decano="Decano")
		carrera = Carrera.objects.create(nombre="Informatica", codigo="INF", facultad=facultad)

		self.assertIsNotNone(facultad.id)
		self.assertEqual(carrera.facultad, facultad)
		self.assertTrue(carrera.activa)

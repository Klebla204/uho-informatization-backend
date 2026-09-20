import uuid

from django.conf import settings
from django.db import models


class PerfilEstudiante(models.Model):
	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil_estudiante")
	carrera = models.ForeignKey("academics.Carrera", on_delete=models.PROTECT, related_name="perfiles_estudiante")
	facultad = models.ForeignKey("academics.Facultad", on_delete=models.PROTECT, related_name="perfiles_estudiante")
	anio = models.PositiveSmallIntegerField(db_column="año")
	tipo_curso = models.CharField(max_length=100)
	matricula = models.CharField(max_length=100, unique=True)

	def __str__(self):
		return f"Perfil de {self.usuario}"

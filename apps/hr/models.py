import uuid

from django.conf import settings
from django.db import models


class Cargo(models.Model):
	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	nombre = models.CharField(max_length=200)
	nivel = models.CharField(max_length=100, blank=True)
	activa = models.BooleanField(default=True)

	def __str__(self):
		return self.nombre


class PerfilTrabajador(models.Model):
	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil_trabajador")
	cargo = models.ForeignKey(Cargo, on_delete=models.PROTECT, related_name="perfiles_trabajador")
	departamento = models.CharField(max_length=200)
	tipo_contrato = models.CharField(max_length=100)

	def __str__(self):
		return f"Perfil de {self.usuario}"

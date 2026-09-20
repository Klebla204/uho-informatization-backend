import uuid

from django.db import models


class Facultad(models.Model):
	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	nombre = models.CharField(max_length=200)
	codigo = models.CharField(max_length=50, unique=True)
	decano = models.CharField(max_length=200, blank=True)
	activa = models.BooleanField(default=True)

	def __str__(self):
		return self.nombre


class Carrera(models.Model):
	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	nombre = models.CharField(max_length=200)
	codigo = models.CharField(max_length=50, unique=True)
	facultad = models.ForeignKey(Facultad, on_delete=models.PROTECT, related_name="carreras")
	activa = models.BooleanField(default=True)

	def __str__(self):
		return self.nombre

from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ("ADMIN", "Administrador"),
        ("PROFESOR", "Profesor"),
        ("ESTUDIANTE", "Estudiante"),
        ("INVESTIGADOR", "Investigador"),
        ("MANTENIMIENTO", "Mantenimiento"),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="ESTUDIANTE")

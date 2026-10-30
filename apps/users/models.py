import uuid

from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models


class EncryptedTextField(models.TextField):
    def _cipher(self):
        key = getattr(settings, "DATA_ENCRYPTION_KEY", "")
        if not key:
            raise ValueError("DATA_ENCRYPTION_KEY must be configured")
        return Fernet(key.encode())

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return self._cipher().decrypt(value.encode()).decode()

    def get_prep_value(self, value):
        if value is None:
            return value
        return self._cipher().encrypt(str(value).encode()).decode()


class CustomUserManager(BaseUserManager):
    def create_user(self, auth_uid, email, **extra_fields):
        if not auth_uid:
            raise ValueError("auth_uid is required")
        if not email:
            raise ValueError("email is required")

        user = self.model(auth_uid=auth_uid, email=self.normalize_email(email), **extra_fields)
        user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, auth_uid, email, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if not extra_fields["is_staff"] or not extra_fields["is_superuser"]:
            raise ValueError("Superuser must have is_staff and is_superuser enabled")

        return self.create_user(auth_uid, email, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    USER_TYPE_CHOICES = [
        ("ESTUDIANTE", "Estudiante"),
        ("TRABAJADOR", "Trabajador"),
        ("BIBLIOTECARIO", "Bibliotecario"),
        ("ADMINISTRADOR", "Administrador"),
        ("SUPER_ADMIN", "Super-Admin"),
    ]
    STATUS_CHOICES = [
        ("ACTIVO", "Activo"),
        ("INACTIVO", "Inactivo"),
        ("BLOQUEADO", "Bloqueado"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    auth_uid = models.CharField(max_length=255, unique=True)
    nombre = models.CharField(max_length=150)
    apellidos = models.CharField(max_length=200)
    ci = EncryptedTextField(unique=True)
    email = models.EmailField(unique=True)
    telefono = EncryptedTextField(blank=True)
    tipo_usuario = models.CharField(max_length=20, choices=USER_TYPE_CHOICES)
    estado = models.CharField(max_length=12, choices=STATUS_CHOICES, default="ACTIVO")
    fecha_registro = models.DateTimeField(auto_now_add=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    objects = CustomUserManager()

    USERNAME_FIELD = "auth_uid"
    REQUIRED_FIELDS = ["email"]

    def __str__(self):
        return f"{self.nombre} {self.apellidos}".strip()

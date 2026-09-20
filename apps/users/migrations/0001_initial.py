import uuid

from django.db import migrations, models

import apps.users.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="CustomUser",
            fields=[
                ("password", models.CharField(max_length=128, verbose_name="password")),
                ("last_login", models.DateTimeField(blank=True, null=True, verbose_name="last login")),
                ("is_superuser", models.BooleanField(default=False, verbose_name="superuser status")),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("auth_uid", models.CharField(max_length=255, unique=True)),
                ("nombre", models.CharField(max_length=150)),
                ("apellidos", models.CharField(max_length=200)),
                ("ci", apps.users.models.EncryptedTextField(unique=True)),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("telefono", apps.users.models.EncryptedTextField(blank=True)),
                (
                    "tipo_usuario",
                    models.CharField(
                        choices=[
                            ("ESTUDIANTE", "Estudiante"),
                            ("TRABAJADOR", "Trabajador"),
                            ("BIBLIOTECARIO", "Bibliotecario"),
                            ("ADMINISTRADOR", "Administrador"),
                            ("SUPER_ADMIN", "Super-Admin"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "estado",
                    models.CharField(
                        choices=[
                            ("ACTIVO", "Activo"),
                            ("INACTIVO", "Inactivo"),
                            ("BLOQUEADO", "Bloqueado"),
                        ],
                        default="ACTIVO",
                        max_length=12,
                    ),
                ),
                ("fecha_registro", models.DateTimeField(auto_now_add=True)),
                ("is_staff", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "groups",
                    models.ManyToManyField(
                        blank=True,
                        related_name="customuser_set",
                        related_query_name="customuser",
                        to="auth.group",
                    ),
                ),
                (
                    "user_permissions",
                    models.ManyToManyField(
                        blank=True,
                        related_name="customuser_set",
                        related_query_name="customuser",
                        to="auth.permission",
                    ),
                ),
            ],
            options={"verbose_name": "user", "verbose_name_plural": "users"},
            managers=[("objects", apps.users.models.CustomUserManager())],
        ),
    ]

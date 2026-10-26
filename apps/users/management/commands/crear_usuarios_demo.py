from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.rbac.models import Role, UserRole
from apps.users.models import CustomUser

from ._dev_auth import require_local_demo_mode


DEMO_USERS = [
    {
        "auth_uid": "demo-estudiante",
        "email": "estudiante.demo@localhost",
        "nombre": "Ana",
        "apellidos": "Estudiante Demo",
        "ci": "00000000001",
        "telefono": "00000001",
        "tipo_usuario": "ESTUDIANTE",
        "role": "estudiante",
    },
    {
        "auth_uid": "demo-trabajador",
        "email": "trabajador.demo@localhost",
        "nombre": "Luis",
        "apellidos": "Trabajador Demo",
        "ci": "00000000002",
        "telefono": "00000002",
        "tipo_usuario": "TRABAJADOR",
        "role": "trabajador",
    },
    {
        "auth_uid": "demo-bibliotecario",
        "email": "bibliotecario.demo@localhost",
        "nombre": "Marta",
        "apellidos": "Bibliotecaria Demo",
        "ci": "00000000003",
        "telefono": "00000003",
        "tipo_usuario": "BIBLIOTECARIO",
        "role": "bibliotecario",
    },
]


class Command(BaseCommand):
    help = "Crea perfiles desechables para probar funcionalidades localmente."

    @transaction.atomic
    def handle(self, *args, **options):
        require_local_demo_mode()
        for data in DEMO_USERS:
            values = {key: value for key, value in data.items() if key != "role"}
            user, created = CustomUser.objects.get_or_create(
                auth_uid=data["auth_uid"],
                defaults={**values, "es_usuario_demo": True},
            )
            if not user.es_usuario_demo:
                raise CommandError(f"{user.auth_uid} existe y no es una cuenta demo; no se modificó.")
            if not created:
                for field, value in values.items():
                    setattr(user, field, value)
            user.set_unusable_password()
            user.save()

            role = Role.objects.filter(name=data["role"]).first()
            if role is None:
                raise CommandError("Faltan roles RBAC; ejecuta primero: python manage.py seed_roles")
            UserRole.objects.get_or_create(user=user, role=role)
            self.stdout.write(f"Cuenta demo disponible: {user.auth_uid} ({data['role']})")

        self.stdout.write(self.style.SUCCESS("Perfiles de demostración listos; no se configuraron contraseñas."))

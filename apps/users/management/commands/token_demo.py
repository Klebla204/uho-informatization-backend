from django.core.management.base import BaseCommand, CommandError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.models import CustomUser

from ._dev_auth import require_local_demo_mode


class Command(BaseCommand):
    help = "Emite un JWT temporal para una cuenta demo local, sin crear un endpoint de login."

    def add_arguments(self, parser):
        parser.add_argument("auth_uid")

    def handle(self, *args, **options):
        require_local_demo_mode()
        user = CustomUser.objects.filter(
            auth_uid=options["auth_uid"],
            es_usuario_demo=True,
            is_active=True,
            estado="ACTIVO",
        ).first()
        if user is None:
            raise CommandError("No existe una cuenta demo activa. Ejecuta primero crear_usuarios_demo.")

        refresh = RefreshToken.for_user(user)
        self.stdout.write(f"Bearer {refresh.access_token}")
        self.stdout.write(f"Refresh {refresh}")
        self.stdout.write(self.style.WARNING("Token temporal local. No usar con cuentas reales ni en producción."))

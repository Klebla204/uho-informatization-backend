from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.catalogo.models import Biblioteca


LIBRARIES = (
    "Sede Oscar Lucero",
    "Sede Manuel Fajardo",
    "Sede Jose de la Luz y Caballero",
    "Sede Celia Sánchez",
)


class Command(BaseCommand):
    help = "Crea las cuatro sedes bibliotecarias iniciales."

    def add_arguments(self, parser):
        parser.add_argument(
            "--responsable-id",
            required=True,
            help="ID del usuario responsable de las sedes.",
        )

    def handle(self, *args, **options):
        user_model = get_user_model()
        try:
            responsible = user_model.objects.get(pk=options["responsable_id"], is_active=True)
        except (user_model.DoesNotExist, ValueError, TypeError) as error:
            raise CommandError("El usuario responsable no existe o no está activo.") from error

        for name in LIBRARIES:
            library, created = Biblioteca.objects.get_or_create(
                nombre=name,
                defaults={"direccion": "Por definir", "responsable": responsible},
            )
            action = "Creada" if created else "Ya existía"
            self.stdout.write(f"{action}: {library.nombre}")
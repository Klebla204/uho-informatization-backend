from django.core.management.base import BaseCommand

from apps.prestamos.vencimientos import notify_due_loans


class Command(BaseCommand):
    help = "Notifica préstamos que vencen en 3 días o menos y préstamos vencidos. Pensado para ejecutarse a diario."

    def handle(self, *args, **options):
        created = notify_due_loans()
        self.stdout.write(
            f"Avisos de próximo vencimiento: {created['por_vencer']}. Avisos de préstamo vencido: {created['vencidos']}."
        )

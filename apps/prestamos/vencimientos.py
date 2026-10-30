from datetime import timedelta

from django.utils import timezone

from .models import Notificacion, Prestamo

REMINDER_DAYS = 3


def local_date(value):
    return timezone.localtime(value).date()


def days_until_due(loan, now=None):
    """Días calendario hasta la devolución pactada; negativo si ya venció."""
    return (local_date(loan.fecha_devolucion_pactada) - local_date(now or timezone.now())).days


def due_windows(now=None):
    """Límites (inicio de hoy, fin de la ventana de aviso) en hora local."""
    start_today = timezone.localtime(now or timezone.now()).replace(hour=0, minute=0, second=0, microsecond=0)
    return start_today, start_today + timedelta(days=REMINDER_DAYS + 1)


def _notify(loan, kind, message):
    _, created = Notificacion.objects.get_or_create(
        prestamo=loan,
        tipo=kind,
        defaults={"usuario": loan.usuario, "mensaje": message},
    )
    return created


def notify_due_loans(*, user=None, now=None):
    """Crea una sola vez el aviso de próximo vencimiento y el de préstamo vencido."""
    now = now or timezone.now()
    loans = Prestamo.objects.filter(estado="ACTIVO").select_related("usuario", "ejemplar__libro")
    if user is not None:
        loans = loans.filter(usuario=user)

    created = {"por_vencer": 0, "vencidos": 0}
    for loan in loans:
        days = days_until_due(loan, now)
        title = loan.ejemplar.libro.titulo
        due = local_date(loan.fecha_devolucion_pactada).strftime("%d/%m/%Y")
        if 0 <= days <= REMINDER_DAYS:
            when = "hoy" if days == 0 else f"en {days} día(s)"
            message = f"Tu préstamo de «{title}» vence el {due} ({when}). Recuerda devolverlo a tiempo."
            created["por_vencer"] += _notify(loan, "POR_VENCER", message)
        elif days < 0:
            message = f"Tu préstamo de «{title}» venció el {due}. Devuélvelo lo antes posible."
            created["vencidos"] += _notify(loan, "VENCIDO", message)
    return created

from django.db import transaction
from django.utils import timezone

from apps.catalogo.models import Ejemplar, Libro

from .models import Prestamo


class LoanRequestError(Exception):
    pass


@transaction.atomic
def request_loan(*, user, book_id, due_date, library_id=None, observations=""):
    if user.estado != "ACTIVO" or not user.is_active:
        raise LoanRequestError("El usuario no está activo.")

    book = Libro.objects.filter(id=book_id, activo=True).first()
    if not book:
        raise LoanRequestError("El libro no existe o está inactivo.")

    available_copies = Ejemplar.objects.select_for_update().filter(
        libro=book,
        estado="DISPONIBLE",
        biblioteca_id=library_id,
    ).exclude(
        prestamos__estado__in={"PENDIENTE", "APROBADO", "LISTO", "ACTIVO"}
    )
    if library_id is None:
        available_copies = Ejemplar.objects.select_for_update().filter(
            libro=book,
            estado="DISPONIBLE",
        ).exclude(
            prestamos__estado__in={"PENDIENTE", "APROBADO", "LISTO", "ACTIVO"}
        )

    copy = available_copies.select_related("biblioteca").first()
    if not copy:
        raise LoanRequestError("No hay ejemplares disponibles para este libro.")

    if due_date <= timezone.now():
        raise LoanRequestError("La fecha de devolución debe ser futura.")

    return Prestamo.objects.create(
        usuario=user,
        ejemplar=copy,
        biblioteca=copy.biblioteca,
        fecha_devolucion_pactada=due_date,
        estado="PENDIENTE",
        observaciones=observations,
    )

from django.db import transaction
from django.utils import timezone

from apps.catalogo.models import Ejemplar, Libro
from apps.users.carnet import profile_complete

from .models import Prestamo


class LoanRequestError(Exception):
    pass


@transaction.atomic
def request_loan(*, user, book_id, library_id=None, observations=""):
    if user.estado != "ACTIVO" or not user.is_active:
        raise LoanRequestError("El usuario no está activo.")
    if not profile_complete(user):
        raise LoanRequestError("Completa tu perfil antes de solicitar un préstamo.")

    book = Libro.objects.filter(id=book_id, activo=True).first()
    if not book:
        raise LoanRequestError("El libro no existe o está inactivo.")

    if Prestamo.objects.filter(
        usuario=user,
        ejemplar__libro=book,
        estado__in={"PENDIENTE", "APROBADO", "LISTO", "ACTIVO"},
    ).exists():
        raise LoanRequestError("Ya solicitaste este libro. Tu solicitud está en curso.")

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

    return Prestamo.objects.create(
        usuario=user,
        ejemplar=copy,
        biblioteca=copy.biblioteca,
        estado="PENDIENTE",
        observaciones=observations,
    )


@transaction.atomic
def create_counter_loan(*, user, librarian, book_id, library_id, due_date, observations=""):
    if user.estado != "ACTIVO" or not user.is_active:
        raise LoanRequestError("El usuario no está activo.")
    if due_date <= timezone.now():
        raise LoanRequestError("La fecha de devolución debe ser futura.")

    book = Libro.objects.filter(id=book_id, activo=True).first()
    if not book:
        raise LoanRequestError("El libro no existe o está inactivo.")

    copy = (
        Ejemplar.objects.select_for_update()
        .select_related("biblioteca")
        .filter(libro=book, biblioteca_id=library_id, estado="DISPONIBLE")
        .exclude(prestamos__estado__in={"PENDIENTE", "APROBADO", "LISTO", "ACTIVO"})
        .first()
    )
    if not copy:
        raise LoanRequestError("No hay ejemplares disponibles en esta biblioteca.")

    copy.estado = "PRESTADO"
    copy.save(update_fields=["estado"])
    return Prestamo.objects.create(
        usuario=user,
        ejemplar=copy,
        biblioteca=copy.biblioteca,
        bibliotecario=librarian,
        fecha_devolucion_pactada=due_date,
        estado="ACTIVO",
        observaciones=observations,
    )

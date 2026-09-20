from django.db import transaction
from django.utils import timezone

from .models import Prestamo


class LibrarianLoanError(Exception):
    pass


@transaction.atomic
def approve_loan(*, loan_id, librarian, pickup_deadline=None):
    loan = _locked_loan(loan_id)
    _require_librarian(librarian)
    if loan.estado != "PENDIENTE":
        raise LibrarianLoanError("Solo se pueden aprobar solicitudes pendientes.")

    loan.bibliotecario = librarian
    loan.fecha_aprobacion = timezone.now()
    loan.fecha_recogida_limite = pickup_deadline
    loan.estado = "LISTO" if pickup_deadline else "APROBADO"
    loan.save(update_fields=["bibliotecario", "fecha_aprobacion", "fecha_recogida_limite", "estado"])
    return loan


@transaction.atomic
def reject_loan(*, loan_id, librarian, reason):
    loan = _locked_loan(loan_id)
    _require_librarian(librarian)
    if loan.estado != "PENDIENTE":
        raise LibrarianLoanError("Solo se pueden rechazar solicitudes pendientes.")

    loan.bibliotecario = librarian
    loan.estado = "RECHAZADO"
    loan.observaciones = reason
    loan.save(update_fields=["bibliotecario", "estado", "observaciones"])
    return loan


@transaction.atomic
def mark_loan_ready(*, loan_id, librarian, pickup_deadline):
    loan = _locked_loan(loan_id)
    _require_librarian(librarian)
    if loan.estado != "APROBADO":
        raise LibrarianLoanError("Solo se pueden preparar solicitudes aprobadas.")
    if pickup_deadline <= timezone.now():
        raise LibrarianLoanError("La fecha límite de recojo debe ser futura.")

    loan.bibliotecario = librarian
    loan.fecha_recogida_limite = pickup_deadline
    loan.estado = "LISTO"
    loan.save(update_fields=["bibliotecario", "fecha_recogida_limite", "estado"])
    return loan


@transaction.atomic
def collect_loan(*, loan_id, librarian):
    loan = _locked_loan(loan_id)
    _require_librarian(librarian)
    if loan.estado not in {"APROBADO", "LISTO"}:
        raise LibrarianLoanError("Solo se puede activar un préstamo aprobado o listo.")

    loan.bibliotecario = librarian
    loan.estado = "ACTIVO"
    loan.ejemplar.estado = "PRESTADO"
    loan.ejemplar.save(update_fields=["estado"])
    loan.save(update_fields=["bibliotecario", "estado"])
    return loan


@transaction.atomic
def return_loan(*, loan_id, librarian):
    loan = _locked_loan(loan_id)
    _require_librarian(librarian)
    if loan.estado != "ACTIVO":
        raise LibrarianLoanError("Solo se pueden devolver préstamos activos.")

    loan.bibliotecario = librarian
    loan.estado = "DEVUELTO"
    loan.fecha_devolucion_real = timezone.now()
    loan.ejemplar.estado = "DISPONIBLE"
    loan.ejemplar.save(update_fields=["estado"])
    loan.save(update_fields=["bibliotecario", "estado", "fecha_devolucion_real"])
    return loan


def _locked_loan(loan_id):
    try:
        return Prestamo.objects.select_for_update().select_related("ejemplar").get(id=loan_id)
    except Prestamo.DoesNotExist as error:
        raise LibrarianLoanError("El préstamo no existe.") from error


def _require_librarian(user):
    if not user.is_authenticated or user.tipo_usuario not in {"BIBLIOTECARIO", "ADMINISTRADOR", "SUPER_ADMIN"}:
        raise LibrarianLoanError("El usuario no tiene permisos de bibliotecario.")

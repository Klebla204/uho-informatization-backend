from django.db import transaction
from django.utils import timezone

from apps.catalogo.models import Libro
from apps.rbac.drf_permissions import user_library_id

from .models import ListaEspera, Notificacion, Prestamo, RenovacionPrestamo


class LibrarianLoanError(Exception):
    pass


@transaction.atomic
def decide_renewal(*, renewal_id, librarian, approve, due_date=None, reason=""):
    try:
        renewal = RenovacionPrestamo.objects.select_for_update().select_related(
            "prestamo__ejemplar__libro", "prestamo__usuario", "prestamo__biblioteca"
        ).get(id=renewal_id)
    except RenovacionPrestamo.DoesNotExist as error:
        raise LibrarianLoanError("La solicitud de renovación no existe.") from error

    loan = renewal.prestamo
    _require_librarian(librarian, loan)
    book = Libro.objects.select_for_update().get(id=loan.ejemplar.libro_id)
    if renewal.estado != "PENDIENTE":
        raise LibrarianLoanError("La solicitud de renovación ya fue procesada.")
    if loan.estado != "ACTIVO":
        raise LibrarianLoanError("Solo se puede procesar la renovación de un préstamo activo.")

    now = timezone.now()
    renewal.bibliotecario = librarian
    renewal.fecha_procesamiento = now
    if approve:
        if due_date is None or due_date <= now:
            raise LibrarianLoanError("La nueva fecha de devolución debe ser futura.")
        if Prestamo.objects.filter(
            ejemplar__libro=book,
            estado__in={"PENDIENTE", "APROBADO", "LISTO"},
        ).exists():
            raise LibrarianLoanError("No se puede aprobar: hay reservas pendientes para este título.")
        renewal.estado = "APROBADA"
        renewal.fecha_devolucion_propuesta = due_date
        loan.fecha_devolucion_pactada = due_date
        loan.save(update_fields=["fecha_devolucion_pactada"])
        message = f'La renovación de "{book.titulo}" fue aprobada. Nueva fecha de devolución: {due_date:%d/%m/%Y}.'
        notification_type = "RENOVACION_APROBADA"
    else:
        renewal.estado = "RECHAZADA"
        renewal.motivo_rechazo = reason
        message = f'La renovación de "{book.titulo}" fue rechazada. {reason}'.strip()
        notification_type = "RENOVACION_RECHAZADA"

    renewal.save()
    Notificacion.objects.create(
        usuario=loan.usuario,
        prestamo=loan,
        tipo=notification_type,
        mensaje=message,
    )
    return renewal


@transaction.atomic
def approve_loan(*, loan_id, librarian, pickup_deadline=None):
    loan = _locked_loan(loan_id)
    _require_librarian(librarian, loan)
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
    _require_librarian(librarian, loan)
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
    _require_librarian(librarian, loan)
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
def collect_loan(*, loan_id, librarian, due_date):
    loan = _locked_loan(loan_id)
    _require_librarian(librarian, loan)
    if loan.estado != "LISTO":
        raise LibrarianLoanError("Solo se puede registrar la entrega de un préstamo listo para recoger.")
    if due_date <= timezone.now():
        raise LibrarianLoanError("La fecha de devolución debe ser futura.")

    loan.bibliotecario = librarian
    loan.fecha_devolucion_pactada = due_date
    loan.estado = "ACTIVO"
    loan.ejemplar.estado = "PRESTADO"
    loan.ejemplar.save(update_fields=["estado"])
    loan.save(update_fields=["bibliotecario", "fecha_devolucion_pactada", "estado"])
    return loan


@transaction.atomic
def return_loan(*, loan_id, librarian):
    loan = _locked_loan(loan_id)
    _require_librarian(librarian, loan)
    if loan.estado != "ACTIVO":
        raise LibrarianLoanError("Solo se pueden devolver préstamos activos.")

    book = Libro.objects.select_for_update().get(id=loan.ejemplar.libro_id)
    loan.bibliotecario = librarian
    loan.estado = "DEVUELTO"
    loan.fecha_devolucion_real = timezone.now()
    loan.ejemplar.estado = "DISPONIBLE"
    loan.ejemplar.save(update_fields=["estado"])
    loan.save(update_fields=["bibliotecario", "estado", "fecha_devolucion_real"])
    _notify_next_waiting_user(book=book, library_name=loan.biblioteca.nombre)
    return loan


def _notify_next_waiting_user(*, book, library_name):
    waiting = (
        ListaEspera.objects.select_for_update()
        .select_related("usuario")
        .filter(libro=book, estado="ACTIVA")
        .order_by("fecha_inscripcion", "id")
        .first()
    )
    if not waiting:
        return

    waiting.estado = "NOTIFICADA"
    waiting.save(update_fields=["estado"])
    Notificacion.objects.create(
        usuario=waiting.usuario,
        tipo="DISPONIBILIDAD",
        mensaje=f'El libro "{book.titulo}" ya tiene un ejemplar disponible en {library_name}.',
    )


def _locked_loan(loan_id):
    try:
        return Prestamo.objects.select_for_update().select_related("ejemplar").get(id=loan_id)
    except Prestamo.DoesNotExist as error:
        raise LibrarianLoanError("El préstamo no existe.") from error


def _require_librarian(user, loan):
    if not user.is_authenticated or user.tipo_usuario not in {"BIBLIOTECARIO", "ADMINISTRADOR", "SUPER_ADMIN"}:
        raise LibrarianLoanError("El usuario no tiene permisos de bibliotecario.")
    library_id = user_library_id(user)
    if library_id and loan.biblioteca_id != library_id:
        raise LibrarianLoanError("El préstamo pertenece a otra sede.")

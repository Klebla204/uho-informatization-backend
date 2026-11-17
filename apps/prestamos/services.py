from django.db import transaction
from django.utils import timezone

from apps.catalogo.models import Ejemplar, Libro
from apps.users.carnet import profile_complete

from .models import ListaEspera, Notificacion, Prestamo, RenovacionPrestamo, Sancion
from .vencimientos import due_windows


class LoanRequestError(Exception):
    pass


class WaitingListError(Exception):
    pass


class RenewalError(Exception):
    pass


class SanctionError(Exception):
    pass


@transaction.atomic
def register_sanction(*, loan_id, librarian, reason=""):
    try:
        loan = Prestamo.objects.select_for_update().select_related("usuario").get(id=loan_id)
    except Prestamo.DoesNotExist as error:
        raise SanctionError("El préstamo no existe.") from error

    user = type(loan.usuario).objects.select_for_update().get(id=loan.usuario_id)
    start_today, _ = due_windows()
    if loan.estado != "ACTIVO" or not loan.fecha_devolucion_pactada or loan.fecha_devolucion_pactada >= start_today:
        raise SanctionError("Solo se puede sancionar por un préstamo activo vencido.")
    if not user.is_active or user.estado == "INACTIVO":
        raise SanctionError("La cuenta del usuario está inactiva.")
    if Sancion.objects.filter(usuario=user, activa=True).exists():
        raise SanctionError("El usuario ya tiene una sanción activa.")

    sanction = Sancion.objects.create(
        usuario=user,
        prestamo=loan,
        bibliotecario=librarian,
        motivo=reason,
    )
    user.estado = "BLOQUEADO"
    user.save(update_fields=["estado"])
    Notificacion.objects.create(
        usuario=user,
        prestamo=loan,
        tipo="SANCION",
        mensaje=f"Tu cuenta fue bloqueada temporalmente por el préstamo vencido de «{loan.ejemplar.libro.titulo}». Contacta a la biblioteca para regularizarlo.",
    )
    return sanction


@transaction.atomic
def unblock_user(*, sanction_id, librarian):
    try:
        sanction = Sancion.objects.select_for_update().select_related("usuario").get(id=sanction_id, activa=True)
    except Sancion.DoesNotExist as error:
        raise SanctionError("La sanción activa no existe.") from error

    sanction.activa = False
    sanction.fecha_desbloqueo = timezone.now()
    sanction.save(update_fields=["activa", "fecha_desbloqueo"])
    user = sanction.usuario
    if user.estado == "BLOQUEADO" and not Sancion.objects.filter(usuario=user, activa=True).exists():
        user.estado = "ACTIVO"
        user.save(update_fields=["estado"])
    Notificacion.objects.create(
        usuario=user,
        prestamo=sanction.prestamo,
        tipo="DESBLOQUEO",
        mensaje="Tu cuenta fue desbloqueada. Ya puedes solicitar préstamos.",
    )
    return sanction


@transaction.atomic
def request_renewal(*, user, loan_id):
    try:
        loan = Prestamo.objects.select_for_update().select_related("ejemplar__libro").get(
            id=loan_id, usuario=user
        )
    except Prestamo.DoesNotExist as error:
        raise RenewalError("El préstamo no existe.") from error

    book = Libro.objects.select_for_update().get(id=loan.ejemplar.libro_id)
    if loan.estado != "ACTIVO":
        raise RenewalError("Solo puedes solicitar la renovación de un préstamo activo.")
    if Prestamo.objects.filter(
        ejemplar__libro=book,
        estado__in={"PENDIENTE", "APROBADO", "LISTO"},
    ).exists():
        raise RenewalError("No se puede renovar: hay reservas pendientes para este título.")
    if RenovacionPrestamo.objects.filter(prestamo=loan, estado="PENDIENTE").exists():
        raise RenewalError("Ya existe una solicitud de renovación pendiente.")

    return RenovacionPrestamo.objects.create(prestamo=loan)


@transaction.atomic
def join_waiting_list(*, user, book_id):
    if user.estado != "ACTIVO" or not user.is_active:
        raise WaitingListError("El usuario no está activo.")

    book = Libro.objects.select_for_update().filter(id=book_id, activo=True).first()
    if not book:
        raise WaitingListError("El libro no existe o está inactivo.")

    if Prestamo.objects.filter(
        usuario=user,
        ejemplar__libro=book,
        estado__in={"PENDIENTE", "APROBADO", "LISTO", "ACTIVO"},
    ).exists():
        raise WaitingListError("Ya tienes una solicitud o préstamo en curso para este libro.")

    has_copies = Ejemplar.objects.filter(libro=book).exists()
    available_copies = Ejemplar.objects.filter(libro=book, estado="DISPONIBLE").exclude(
        prestamos__estado__in={"PENDIENTE", "APROBADO", "LISTO", "ACTIVO"}
    )
    if not has_copies:
        raise WaitingListError("Este libro todavía no tiene ejemplares registrados.")
    if available_copies.exists():
        raise WaitingListError("El libro tiene ejemplares disponibles; puedes solicitar un préstamo.")

    return ListaEspera.objects.get_or_create(usuario=user, libro=book, estado="ACTIVA")


@transaction.atomic
def request_loan(*, user, book_id, library_id=None, observations=""):
    if user.estado != "ACTIVO" or not user.is_active:
        raise LoanRequestError("El usuario no está activo.")
    if not profile_complete(user):
        raise LoanRequestError("Completa tu perfil antes de solicitar un préstamo.")

    book = Libro.objects.select_for_update().filter(id=book_id, activo=True).first()
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

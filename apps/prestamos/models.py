import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Prestamo(models.Model):
    STATUS_CHOICES = [
        ("PENDIENTE", "Pendiente"),
        ("APROBADO", "Aprobado"),
        ("LISTO", "Listo para recoger"),
        ("ACTIVO", "Activo"),
        ("DEVUELTO", "Devuelto"),
        ("VENCIDO", "Vencido"),
        ("RECHAZADO", "Rechazado"),
        ("CANCELADO", "Cancelado"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="prestamos")
    ejemplar = models.ForeignKey("catalogo.Ejemplar", on_delete=models.PROTECT, related_name="prestamos")
    biblioteca = models.ForeignKey("catalogo.Biblioteca", on_delete=models.PROTECT, related_name="prestamos")
    bibliotecario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="prestamos_gestionados",
    )
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    fecha_aprobacion = models.DateTimeField(null=True, blank=True)
    fecha_recogida_limite = models.DateTimeField(null=True, blank=True)
    fecha_devolucion_pactada = models.DateTimeField()
    fecha_devolucion_real = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(max_length=12, choices=STATUS_CHOICES, default="PENDIENTE")
    observaciones = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["usuario"]),
            models.Index(fields=["estado"]),
        ]

    def clean(self):
        if self.estado in {"DEVUELTO", "VENCIDO"} and not self.fecha_devolucion_real:
            raise ValidationError({"fecha_devolucion_real": "Este estado requiere fecha de devolución real."})

    def __str__(self):
        return f"{self.usuario} - {self.ejemplar}"


class ListaEspera(models.Model):
    STATUS_CHOICES = [
        ("ACTIVA", "Activa"),
        ("NOTIFICADA", "Notificada"),
        ("CANCELADA", "Cancelada"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="listas_espera")
    libro = models.ForeignKey("catalogo.Libro", on_delete=models.PROTECT, related_name="listas_espera")
    fecha_inscripcion = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=12, choices=STATUS_CHOICES, default="ACTIVA")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["usuario", "libro"],
                condition=models.Q(estado="ACTIVA"),
                name="unique_active_waiting_list_entry",
            ),
        ]


class Notificacion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="notificaciones")
    tipo = models.CharField(max_length=100)
    mensaje = models.TextField()
    leida = models.BooleanField(default=False)
    fecha_envio = models.DateTimeField(auto_now_add=True)
    prestamo = models.ForeignKey(
        Prestamo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notificaciones",
    )


class Carnet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="carnet")
    codigo_qr = models.CharField(max_length=500, unique=True)
    fecha_generacion = models.DateTimeField(auto_now_add=True)
    pdf_url = models.URLField(blank=True)
    activo = models.BooleanField(default=True)

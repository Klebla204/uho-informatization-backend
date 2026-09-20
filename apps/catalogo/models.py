import uuid

from django.conf import settings
from django.db import models


class Biblioteca(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nombre = models.CharField(max_length=200)
    facultad_asociada = models.CharField(max_length=200, blank=True)
    direccion = models.CharField(max_length=300)
    telefono = models.CharField(max_length=30, blank=True)
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="bibliotecas_responsable",
    )
    activa = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class Autor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nombre = models.CharField(max_length=150)
    apellidos = models.CharField(max_length=200)
    nacionalidad = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.nombre} {self.apellidos}".strip()


class Categoria(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    categoria_padre = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="subcategorias",
    )
    activa = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class Editorial(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nombre = models.CharField(max_length=200)
    pais = models.CharField(max_length=100, blank=True)
    activa = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class Libro(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    titulo = models.CharField(max_length=500)
    isbn = models.CharField(max_length=20, unique=True, null=True, blank=True, db_index=True)
    anio_edicion = models.PositiveIntegerField(null=True, blank=True)
    editorial = models.ForeignKey(Editorial, on_delete=models.PROTECT, related_name="libros")
    edicion = models.CharField(max_length=100, blank=True)
    resumen = models.TextField(blank=True)
    portada_url = models.URLField(blank=True)
    activo = models.BooleanField(default=True)
    autores = models.ManyToManyField(Autor, related_name="libros")
    categorias = models.ManyToManyField(Categoria, related_name="libros")

    def __str__(self):
        return self.titulo


class Ejemplar(models.Model):
    STATUS_CHOICES = [
        ("DISPONIBLE", "Disponible"),
        ("PRESTADO", "Prestado"),
        ("DANADO", "Dañado"),
        ("BAJA", "Baja"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    libro = models.ForeignKey(Libro, on_delete=models.PROTECT, related_name="ejemplares")
    biblioteca = models.ForeignKey(Biblioteca, on_delete=models.PROTECT, related_name="ejemplares")
    codigo_ejemplar = models.CharField(max_length=100, unique=True)
    estado = models.CharField(max_length=12, choices=STATUS_CHOICES, default="DISPONIBLE")
    ubicacion_fisica = models.CharField(max_length=300, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["libro"]),
        ]

    def __str__(self):
        return self.codigo_ejemplar

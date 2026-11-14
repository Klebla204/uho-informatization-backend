import uuid

from django.db import transaction
from rest_framework import serializers

from apps.rbac.drf_permissions import user_library_id

from .models import Autor, Biblioteca, Categoria, Editorial, Ejemplar, Libro


class AutorCrudSerializer(serializers.ModelSerializer):
    class Meta:
        model = Autor
        fields = ("id", "nombre", "apellidos", "nacionalidad")
        read_only_fields = ("id",)


class CategoriaCrudSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = ("id", "nombre", "descripcion", "categoria_padre", "activa")
        read_only_fields = ("id",)


class EditorialCrudSerializer(serializers.ModelSerializer):
    class Meta:
        model = Editorial
        fields = ("id", "nombre", "pais", "activa")
        read_only_fields = ("id",)


class BibliotecaCrudSerializer(serializers.ModelSerializer):
    class Meta:
        model = Biblioteca
        fields = (
            "id",
            "nombre",
            "facultad_asociada",
            "direccion",
            "telefono",
            "responsable",
            "activa",
        )
        read_only_fields = ("id",)


class LibroCrudSerializer(serializers.ModelSerializer):
    cantidad_ejemplares = serializers.IntegerField(
        write_only=True,
        required=False,
        min_value=0,
        default=0,
    )

    def validate(self, attrs):
        request = self.context.get("request")
        assigned_library = user_library_id(request.user) if request else None
        if assigned_library and self.instance and not self.instance.ejemplares.filter(biblioteca_id=assigned_library).exists():
            raise serializers.ValidationError("El título no pertenece a tu sede.")
        if not self.instance and assigned_library and attrs.get("cantidad_ejemplares", 0) < 1:
            raise serializers.ValidationError({"cantidad_ejemplares": "Debes crear al menos un ejemplar para tu sede."})
        if not self.instance and attrs.get("cantidad_ejemplares", 0) and not assigned_library:
            raise serializers.ValidationError({"cantidad_ejemplares": "La cuenta debe estar vinculada a una sede para crear ejemplares."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        quantity = validated_data.pop("cantidad_ejemplares", 0)
        book = super().create(validated_data)
        library_id = user_library_id(self.context["request"].user)
        for _ in range(quantity):
            Ejemplar.objects.create(
                libro=book,
                biblioteca_id=library_id,
                codigo_ejemplar=f"{book.id}-{uuid.uuid4().hex[:12]}",
            )
        return book

    class Meta:
        model = Libro
        fields = (
            "id",
            "titulo",
            "isbn",
            "anio_edicion",
            "editorial",
            "edicion",
            "resumen",
            "portada_url",
            "activo",
            "autores",
            "categorias",
            "cantidad_ejemplares",
        )
        read_only_fields = ("id",)


class EjemplarCrudSerializer(serializers.ModelSerializer):
    def validate_biblioteca(self, library):
        request = self.context.get("request")
        assigned_library = user_library_id(request.user) if request else None
        if assigned_library and library.id != assigned_library:
            raise serializers.ValidationError("Solo puedes gestionar ejemplares de tu sede.")
        return library

    class Meta:
        model = Ejemplar
        fields = (
            "id",
            "libro",
            "biblioteca",
            "codigo_ejemplar",
            "estado",
            "ubicacion_fisica",
        )
        read_only_fields = ("id",)

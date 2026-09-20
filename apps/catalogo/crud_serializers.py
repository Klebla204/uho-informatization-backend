from rest_framework import serializers

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
        )
        read_only_fields = ("id",)


class EjemplarCrudSerializer(serializers.ModelSerializer):
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

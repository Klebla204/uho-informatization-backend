from rest_framework import serializers

from .models import Autor, Categoria, Editorial, Ejemplar, Libro


class AutorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Autor
        fields = ("id", "nombre", "apellidos", "nacionalidad")


class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = ("id", "nombre", "descripcion", "categoria_padre", "activa")


class EditorialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Editorial
        fields = ("id", "nombre", "pais", "activa")


class EjemplarSerializer(serializers.ModelSerializer):
    biblioteca_nombre = serializers.CharField(source="biblioteca.nombre", read_only=True)

    class Meta:
        model = Ejemplar
        fields = (
            "id",
            "biblioteca",
            "biblioteca_nombre",
            "codigo_ejemplar",
            "estado",
            "ubicacion_fisica",
        )


class LibroListSerializer(serializers.ModelSerializer):
    autores = AutorSerializer(many=True, read_only=True)
    categorias = CategoriaSerializer(many=True, read_only=True)
    editorial = EditorialSerializer(read_only=True)
    ejemplares_totales = serializers.IntegerField(read_only=True)
    ejemplares_disponibles = serializers.IntegerField(read_only=True)

    class Meta:
        model = Libro
        fields = (
            "id",
            "titulo",
            "isbn",
            "anio_edicion",
            "edicion",
            "portada_url",
            "activo",
            "autores",
            "categorias",
            "editorial",
            "ejemplares_totales",
            "ejemplares_disponibles",
        )


class LibroDetailSerializer(LibroListSerializer):
    resumen = serializers.CharField()
    ejemplares = EjemplarSerializer(many=True, read_only=True)

    class Meta(LibroListSerializer.Meta):
        fields = LibroListSerializer.Meta.fields + ("resumen", "ejemplares")

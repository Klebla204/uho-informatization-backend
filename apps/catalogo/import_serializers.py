from rest_framework import serializers


class CollectionImportSerializer(serializers.Serializer):
    file = serializers.FileField(help_text="Archivo Excel .xlsx con la plantilla de colecciones.")


class CollectionImportResultSerializer(serializers.Serializer):
    filas_procesadas = serializers.IntegerField()
    libros_creados = serializers.IntegerField()
    libros_actualizados = serializers.IntegerField()
    ejemplares_creados = serializers.IntegerField()
    errores = serializers.ListField(child=serializers.DictField())

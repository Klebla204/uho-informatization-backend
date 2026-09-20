from django.contrib import admin

from .models import Autor, Biblioteca, Categoria, Editorial, Ejemplar, Libro


@admin.register(Biblioteca)
class BibliotecaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "facultad_asociada", "activa")
    list_filter = ("activa",)
    search_fields = ("nombre", "direccion")


@admin.register(Autor)
class AutorAdmin(admin.ModelAdmin):
    list_display = ("nombre", "apellidos", "nacionalidad")
    search_fields = ("nombre", "apellidos")


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "categoria_padre", "activa")
    list_filter = ("activa",)
    search_fields = ("nombre",)


@admin.register(Editorial)
class EditorialAdmin(admin.ModelAdmin):
    list_display = ("nombre", "pais", "activa")
    list_filter = ("activa",)
    search_fields = ("nombre",)


@admin.register(Libro)
class LibroAdmin(admin.ModelAdmin):
    list_display = ("titulo", "isbn", "editorial", "activo")
    list_filter = ("activo", "categorias")
    search_fields = ("titulo", "isbn")
    filter_horizontal = ("autores", "categorias")


@admin.register(Ejemplar)
class EjemplarAdmin(admin.ModelAdmin):
    list_display = ("codigo_ejemplar", "libro", "biblioteca", "estado")
    list_filter = ("estado", "biblioteca")
    search_fields = ("codigo_ejemplar", "libro__titulo")
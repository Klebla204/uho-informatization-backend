from django.contrib import admin

from .models import Carrera, Facultad


@admin.register(Facultad)
class FacultadAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo", "decano", "activa")
    search_fields = ("nombre", "codigo")


@admin.register(Carrera)
class CarreraAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo", "facultad", "activa")
    list_filter = ("facultad", "activa")
    search_fields = ("nombre", "codigo")

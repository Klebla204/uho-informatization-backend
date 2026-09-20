from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from apps.rbac.drf_permissions import HasCatalogPermission

from .crud_serializers import (
    AutorCrudSerializer,
    BibliotecaCrudSerializer,
    CategoriaCrudSerializer,
    EditorialCrudSerializer,
    EjemplarCrudSerializer,
    LibroCrudSerializer,
)
from .models import Autor, Biblioteca, Categoria, Editorial, Ejemplar, Libro


class CatalogCrudViewSet(ModelViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, HasCatalogPermission)


class AutorCrudViewSet(CatalogCrudViewSet):
    queryset = Autor.objects.all().order_by("apellidos", "nombre")
    serializer_class = AutorCrudSerializer


class CategoriaCrudViewSet(CatalogCrudViewSet):
    queryset = Categoria.objects.all().order_by("nombre")
    serializer_class = CategoriaCrudSerializer


class EditorialCrudViewSet(CatalogCrudViewSet):
    queryset = Editorial.objects.all().order_by("nombre")
    serializer_class = EditorialCrudSerializer


class BibliotecaCrudViewSet(CatalogCrudViewSet):
    queryset = Biblioteca.objects.all().order_by("nombre")
    serializer_class = BibliotecaCrudSerializer


class LibroCrudViewSet(CatalogCrudViewSet):
    queryset = Libro.objects.prefetch_related("autores", "categorias").select_related("editorial").order_by("titulo")
    serializer_class = LibroCrudSerializer


class EjemplarCrudViewSet(CatalogCrudViewSet):
    queryset = Ejemplar.objects.select_related("libro", "biblioteca").order_by("codigo_ejemplar")
    serializer_class = EjemplarCrudSerializer

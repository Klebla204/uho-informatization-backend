from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework.viewsets import ModelViewSet

from apps.rbac.drf_permissions import HasCatalogPermission
from apps.rbac.drf_permissions import user_library_id

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

    def get_queryset(self):
        queryset = super().get_queryset()
        library_id = user_library_id(self.request.user)
        return queryset.filter(id=library_id) if library_id else queryset

    def perform_create(self, serializer):
        if user_library_id(self.request.user):
            raise PermissionDenied("Solo el superadministrador puede crear bibliotecas.")
        serializer.save()


class LibroCrudViewSet(CatalogCrudViewSet):
    queryset = Libro.objects.prefetch_related("autores", "categorias").select_related("editorial").order_by("titulo")
    serializer_class = LibroCrudSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        library_id = user_library_id(self.request.user)
        if library_id:
            queryset = queryset.filter(ejemplares__biblioteca_id=library_id).distinct()
        return queryset

    def perform_destroy(self, instance):
        instance.activo = False
        instance.save(update_fields=["activo"])


class EjemplarCrudViewSet(CatalogCrudViewSet):
    queryset = Ejemplar.objects.select_related("libro", "biblioteca").order_by("codigo_ejemplar")
    serializer_class = EjemplarCrudSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        assigned_library = user_library_id(self.request.user)
        if assigned_library:
            queryset = queryset.filter(biblioteca_id=assigned_library)
        book_id = self.request.query_params.get("libro")
        library_id = self.request.query_params.get("biblioteca")
        if book_id:
            queryset = queryset.filter(libro_id=book_id)
        if library_id:
            if not assigned_library or str(assigned_library) == library_id:
                queryset = queryset.filter(biblioteca_id=library_id)
            else:
                return queryset.none()
        return queryset

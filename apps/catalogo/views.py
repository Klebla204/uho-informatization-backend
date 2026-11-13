from django.db.models import Count, Exists, IntegerField, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce, Lower
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny

from apps.prestamos.models import Prestamo

from .models import Biblioteca, Categoria, Ejemplar, Libro
from .serializers import (
    BibliotecaPublicSerializer,
    CategoriaPublicSerializer,
    LibroDetailSerializer,
    LibroListSerializer,
)


class CatalogBookQuerysetMixin:
    permission_classes = (AllowAny,)

    def get_queryset(self):
        reserved = Prestamo.objects.filter(
            ejemplar=OuterRef("pk"),
            estado__in=["PENDIENTE", "APROBADO", "LISTO", "ACTIVO"],
        )
        available = (
            Ejemplar.objects.filter(libro=OuterRef("pk"), estado="DISPONIBLE")
            .annotate(reservado=Exists(reserved))
            .filter(reservado=False)
            .order_by()
            .values("libro")
            .annotate(total=Count("pk"))
            .values("total")
        )
        queryset = (
            Libro.objects.filter(activo=True)
            .select_related("editorial")
            .prefetch_related("autores", "categorias", "ejemplares__biblioteca")
            .annotate(
                ejemplares_totales=Count("ejemplares", distinct=True),
                ejemplares_disponibles=Coalesce(Subquery(available, output_field=IntegerField()), 0),
            )
            .order_by(Lower("titulo"))
        )

        search = self.request.query_params.get("q", "").strip()
        if search:
            queryset = queryset.filter(
                Q(titulo__icontains=search)
                | Q(isbn__icontains=search)
                | Q(autores__nombre__icontains=search)
                | Q(autores__apellidos__icontains=search)
            ).distinct()

        categoria = self.request.query_params.get("categoria")
        if categoria:
            queryset = queryset.filter(
                Q(categorias__id=categoria) | Q(categorias__nombre__icontains=categoria)
            ).distinct()

        biblioteca = self.request.query_params.get("biblioteca")
        if biblioteca:
            queryset = queryset.filter(
                Q(ejemplares__biblioteca__id=biblioteca)
                | Q(ejemplares__biblioteca__nombre__icontains=biblioteca)
            ).distinct()

        disponibilidad = self.request.query_params.get("disponibilidad", "").lower()
        if disponibilidad in {"disponible", "true", "1"}:
            queryset = queryset.filter(ejemplares_disponibles__gt=0)
        elif disponibilidad in {"no_disponible", "false", "0"}:
            queryset = queryset.filter(ejemplares_disponibles=0)

        return queryset


class LibroListView(CatalogBookQuerysetMixin, ListAPIView):
    serializer_class = LibroListSerializer

    @extend_schema(
        summary="Consultar catálogo de libros",
        description="Lista libros activos e informa ejemplares totales y disponibles. La disponibilidad excluye ejemplares reservados o prestados.",
        parameters=[
            OpenApiParameter("q", OpenApiTypes.STR, description="Buscar por título, ISBN o autor."),
            OpenApiParameter("categoria", OpenApiTypes.STR, description="UUID o nombre de categoría."),
            OpenApiParameter("biblioteca", OpenApiTypes.STR, description="UUID o nombre de biblioteca."),
            OpenApiParameter("disponibilidad", OpenApiTypes.STR, enum=["disponible", "no_disponible"], description="Filtra por disponibilidad de ejemplares."),
        ],
        responses=LibroListSerializer(many=True),
        auth=[],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class LibroDetailView(CatalogBookQuerysetMixin, RetrieveAPIView):
    serializer_class = LibroDetailSerializer
    lookup_field = "id"
    lookup_url_kwarg = "libro_id"

    @extend_schema(
        summary="Consultar libro y disponibilidad por ejemplar",
        description="Devuelve la ficha del libro y cada ejemplar con su biblioteca, estado y campo disponible.",
        responses=LibroDetailSerializer,
        auth=[],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class BibliotecaListView(ListAPIView):
    permission_classes = (AllowAny,)
    serializer_class = BibliotecaPublicSerializer
    queryset = Biblioteca.objects.filter(activa=True).order_by("nombre")

    @extend_schema(summary="Listar bibliotecas activas", responses=BibliotecaPublicSerializer(many=True), auth=[])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class CategoriaListView(ListAPIView):
    permission_classes = (AllowAny,)
    serializer_class = CategoriaPublicSerializer
    queryset = Categoria.objects.filter(activa=True).order_by("nombre")

    @extend_schema(summary="Listar categorías activas", responses=CategoriaPublicSerializer(many=True), auth=[])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

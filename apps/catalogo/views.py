from django.db.models import Count, Q
from django.db.models.functions import Lower
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny

from .models import Libro
from .serializers import LibroDetailSerializer, LibroListSerializer


class CatalogBookQuerysetMixin:
    permission_classes = (AllowAny,)

    def get_queryset(self):
        queryset = (
            Libro.objects.filter(activo=True)
            .select_related("editorial")
            .prefetch_related("autores", "categorias", "ejemplares__biblioteca")
            .annotate(
                ejemplares_totales=Count("ejemplares", distinct=True),
                ejemplares_disponibles=Count(
                    "ejemplares",
                    filter=Q(ejemplares__estado="DISPONIBLE"),
                    distinct=True,
                ),
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
            queryset = queryset.filter(ejemplares__estado="DISPONIBLE").distinct()
        elif disponibilidad in {"no_disponible", "false", "0"}:
            queryset = queryset.exclude(ejemplares__estado="DISPONIBLE").distinct()

        return queryset


class LibroListView(CatalogBookQuerysetMixin, ListAPIView):
    serializer_class = LibroListSerializer


class LibroDetailView(CatalogBookQuerysetMixin, RetrieveAPIView):
    serializer_class = LibroDetailSerializer
    lookup_field = "id"
    lookup_url_kwarg = "libro_id"

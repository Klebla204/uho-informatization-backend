from django.urls import path

from .views import BibliotecaListView, CategoriaListView, LibroDetailView, LibroListView


urlpatterns = [
    path("bibliotecas/", BibliotecaListView.as_view(), name="biblioteca_list"),
    path("categorias/", CategoriaListView.as_view(), name="categoria_list"),
    path("libros/", LibroListView.as_view(), name="libro_list"),
    path("libros/<uuid:libro_id>/", LibroDetailView.as_view(), name="libro_detail"),
]

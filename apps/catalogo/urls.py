from django.urls import path

from .views import LibroDetailView, LibroListView


urlpatterns = [
    path("libros/", LibroListView.as_view(), name="libro_list"),
    path("libros/<uuid:libro_id>/", LibroDetailView.as_view(), name="libro_detail"),
]

from rest_framework.routers import DefaultRouter
from django.urls import path

from .crud_views import (
    AutorCrudViewSet,
    BibliotecaCrudViewSet,
    CategoriaCrudViewSet,
    EditorialCrudViewSet,
    EjemplarCrudViewSet,
    LibroCrudViewSet,
)
from .import_views import CollectionImportView


router = DefaultRouter()
router.register("autores", AutorCrudViewSet, basename="admin-autor")
router.register("categorias", CategoriaCrudViewSet, basename="admin-categoria")
router.register("editoriales", EditorialCrudViewSet, basename="admin-editorial")
router.register("bibliotecas", BibliotecaCrudViewSet, basename="admin-biblioteca")
router.register("libros", LibroCrudViewSet, basename="admin-libro")
router.register("ejemplares", EjemplarCrudViewSet, basename="admin-ejemplar")

urlpatterns = [
    path("importar/", CollectionImportView.as_view(), name="catalogo-importar"),
] + router.urls

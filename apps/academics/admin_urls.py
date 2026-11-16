from rest_framework.routers import DefaultRouter

from .admin_views import CargoCrudViewSet, CareerCrudViewSet, FacultyCrudViewSet

router = DefaultRouter()
router.register("facultades", FacultyCrudViewSet, basename="admin-facultad")
router.register("carreras", CareerCrudViewSet, basename="admin-carrera")
router.register("cargos", CargoCrudViewSet, basename="admin-cargo")

urlpatterns = router.urls

from django.urls import path
from .views import HelloUHO, HealthCheckView

urlpatterns = [
    path("", HelloUHO.as_view(), name="hello_uho"),
    path("health/", HealthCheckView.as_view(), name="health_check"),
]
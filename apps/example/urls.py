from django.urls import path
from .views import HelloUHO

urlpatterns = [
    path("", HelloUHO.as_view(), name="hello_uho"),
]
from django.urls import path

from .views import MyCardView, MyProfileView

urlpatterns = [
    path("mi-perfil/", MyProfileView.as_view(), name="my_profile"),
    path("mi-carnet/", MyCardView.as_view(), name="my_card"),
]

from django.urls import path

from .views import CareerListView, FacultyListView, MyCardPdfView, MyCardView, MyProfileView

urlpatterns = [
    path("mi-perfil/", MyProfileView.as_view(), name="my_profile"),
    path("mi-carnet/", MyCardView.as_view(), name="my_card"),
    path("mi-carnet/pdf/", MyCardPdfView.as_view(), name="my_card_pdf"),
    path("facultades/", FacultyListView.as_view(), name="faculty_list"),
    path("carreras/", CareerListView.as_view(), name="career_list"),
]

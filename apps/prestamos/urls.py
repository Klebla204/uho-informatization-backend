from django.urls import path

from .views import LoanRequestView


urlpatterns = [
    path("solicitar/", LoanRequestView.as_view(), name="loan_request"),
]

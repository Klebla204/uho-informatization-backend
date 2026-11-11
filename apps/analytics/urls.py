from django.urls import path

from .views import ReportsBaseView, ReportsExportView

urlpatterns = [
    path("", ReportsBaseView.as_view(), name="reports-summary"),
    path("exportar/", ReportsExportView.as_view(), name="reports-export"),
]

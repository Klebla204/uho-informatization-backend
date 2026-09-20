from django.urls import path

from .views import LoanRequestView
from .librarian_views import (
    ApproveLoanView,
    CollectLoanView,
    MarkLoanReadyView,
    RejectLoanView,
    ReturnLoanView,
)


urlpatterns = [
    path("solicitar/", LoanRequestView.as_view(), name="loan_request"),
    path("<uuid:loan_id>/aprobar/", ApproveLoanView.as_view(), name="loan_approve"),
    path("<uuid:loan_id>/rechazar/", RejectLoanView.as_view(), name="loan_reject"),
    path("<uuid:loan_id>/listo/", MarkLoanReadyView.as_view(), name="loan_ready"),
    path("<uuid:loan_id>/recoger/", CollectLoanView.as_view(), name="loan_collect"),
    path("<uuid:loan_id>/devolver/", ReturnLoanView.as_view(), name="loan_return"),
]

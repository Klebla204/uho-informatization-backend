from django.urls import path

from .views import LoanRequestView, RenewalRequestView, WaitingListView
from .list_views import (
    ActiveLoansView,
    DueLoansView,
    MarkNotificationReadView,
    MyLoansView,
    MyNotificationsView,
    PendingLoansView,
    RequestsInProgressView,
    SanctionsView,
    UnblockUserView,
    UserLookupView,
)
from .librarian_views import (
    ApproveLoanView,
    CollectLoanView,
    MarkLoanReadyView,
    RejectLoanView,
    ReturnLoanView,
    CounterLoanView,
    RenewalQueueView,
)


urlpatterns = [
    path("mis-prestamos/", MyLoansView.as_view(), name="my_loans"),
    path("pendientes/", PendingLoansView.as_view(), name="pending_loans"),
    path("solicitudes/", RequestsInProgressView.as_view(), name="requests_in_progress"),
    path("en-curso/", ActiveLoansView.as_view(), name="active_loans"),
    path("vencimientos/", DueLoansView.as_view(), name="due_loans"),
    path("sanciones/", SanctionsView.as_view(), name="sanctions"),
    path("sanciones/<uuid:sanction_id>/desbloquear/", UnblockUserView.as_view(), name="sanction_unblock"),
    path("notificaciones/", MyNotificationsView.as_view(), name="my_notifications"),
    path("notificaciones/leer-todas/", MarkNotificationReadView.as_view(), name="notifications_read_all"),
    path("notificaciones/<uuid:notification_id>/leer/", MarkNotificationReadView.as_view(), name="notification_read"),
    path("usuarios/", UserLookupView.as_view(), name="user_lookup"),
    path("presencial/", CounterLoanView.as_view(), name="counter_loan"),
    path("solicitar/", LoanRequestView.as_view(), name="loan_request"),
    path("lista-espera/", WaitingListView.as_view(), name="waiting_list"),
    path("renovaciones/", RenewalQueueView.as_view(), name="renewal_queue"),
    path("renovaciones/<uuid:renewal_id>/resolver/", RenewalQueueView.as_view(), name="renewal_decide"),
    path("<uuid:loan_id>/aprobar/", ApproveLoanView.as_view(), name="loan_approve"),
    path("<uuid:loan_id>/rechazar/", RejectLoanView.as_view(), name="loan_reject"),
    path("<uuid:loan_id>/listo/", MarkLoanReadyView.as_view(), name="loan_ready"),
    path("<uuid:loan_id>/recoger/", CollectLoanView.as_view(), name="loan_collect"),
    path("<uuid:loan_id>/devolver/", ReturnLoanView.as_view(), name="loan_return"),
    path("<uuid:loan_id>/renovar/", RenewalRequestView.as_view(), name="renewal_request"),
]

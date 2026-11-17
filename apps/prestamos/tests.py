from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from django.utils import timezone

from apps.academics.models import Carrera, Facultad
from apps.catalogo.models import Autor, Biblioteca, Categoria, Editorial, Ejemplar, Libro
from apps.students.models import PerfilEstudiante
from apps.users.models import CustomUser
from apps.auditoria.models import LogsAuditoria

from .models import Carnet, ListaEspera, Notificacion, Prestamo, RenovacionPrestamo, Sancion
from .vencimientos import due_windows


class LoanModelTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            auth_uid="borrower-1",
            email="borrower@example.com",
            nombre="Ana",
            apellidos="Perez",
            ci="01020304060",
            tipo_usuario="ESTUDIANTE",
        )
        self.librarian = CustomUser.objects.create_user(
            auth_uid="librarian-3",
            email="librarian3@example.com",
            nombre="Marta",
            apellidos="Diaz",
            ci="01020304061",
            tipo_usuario="BIBLIOTECARIO",
        )
        self.library = Biblioteca.objects.create(nombre="Central", direccion="Calle 1", responsable=self.librarian)
        publisher = Editorial.objects.create(nombre="Alfaomega")
        author = Autor.objects.create(nombre="Luis", apellidos="Joyanes")
        category = Categoria.objects.create(nombre="Programacion")
        self.book = Libro.objects.create(titulo="Fundamentos", editorial=publisher)
        self.book.autores.add(author)
        self.book.categorias.add(category)
        self.copy = Ejemplar.objects.create(
            libro=self.book,
            biblioteca=self.library,
            codigo_ejemplar="CENT-001",
        )

    def test_loan_relates_user_copy_library_and_librarian(self):
        loan = Prestamo.objects.create(
            usuario=self.user,
            ejemplar=self.copy,
            biblioteca=self.library,
            bibliotecario=self.librarian,
            fecha_devolucion_pactada=timezone.now() + timedelta(days=14),
        )

        self.assertIsNotNone(loan.id)
        self.assertEqual(loan.estado, "PENDIENTE")
        self.assertEqual(loan.ejemplar, self.copy)

    def test_returned_or_overdue_loan_requires_real_return_date(self):
        loan = Prestamo(
            usuario=self.user,
            ejemplar=self.copy,
            biblioteca=self.library,
            bibliotecario=self.librarian,
            fecha_devolucion_pactada=timezone.now() + timedelta(days=14),
            estado="DEVUELTO",
        )

        with self.assertRaises(ValidationError):
            loan.full_clean()

    def test_waiting_list_notifications_and_card_are_related_to_user(self):
        waiting = ListaEspera.objects.create(usuario=self.user, libro=self.book)
        notification = Notificacion.objects.create(
            usuario=self.user,
            tipo="DISPONIBILIDAD",
            mensaje="El ejemplar está disponible.",
        )
        card = Carnet.objects.create(usuario=self.user, codigo_qr="user:borrower-1")

        self.assertEqual(waiting.libro, self.book)
        self.assertFalse(notification.leida)
        self.assertTrue(card.activo)


class OnlineLoanRequestApiTests(APITestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            auth_uid="api-borrower",
            email="api-borrower@example.com",
            nombre="Ana",
            apellidos="Perez",
            ci="01020304062",
            telefono="55512345",
            tipo_usuario="ESTUDIANTE",
        )
        faculty = Facultad.objects.create(nombre="Técnica", codigo="FT")
        career = Carrera.objects.create(nombre="Informática", codigo="INF", facultad=faculty)
        PerfilEstudiante.objects.create(
            usuario=self.user, carrera=career, facultad=faculty, anio=2, tipo_curso="Diurno", matricula="M-API"
        )
        librarian = CustomUser.objects.create_user(
            auth_uid="api-librarian",
            email="api-librarian@example.com",
            nombre="Marta",
            apellidos="Diaz",
            ci="01020304063",
            tipo_usuario="BIBLIOTECARIO",
        )
        self.library = Biblioteca.objects.create(nombre="Central", direccion="Calle 1", responsable=librarian)
        librarian.biblioteca = self.library
        librarian.save(update_fields=["biblioteca"])
        publisher = Editorial.objects.create(nombre="Editorial UHO")
        self.book = Libro.objects.create(titulo="Libro solicitado", editorial=publisher)
        self.copy = Ejemplar.objects.create(
            libro=self.book,
            biblioteca=self.library,
            codigo_ejemplar="LOAN-001",
        )

    def test_authenticated_user_can_request_available_book(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            reverse("loan_request"),
            {
                "libro": str(self.book.id),
                "biblioteca": str(self.library.id),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["estado"], "PENDIENTE")
        self.assertEqual(response.json()["biblioteca"], str(self.library.id))
        self.assertEqual(response.json()["ejemplar"], str(self.copy.id))
        self.assertIsNone(response.json()["bibliotecario"])
        self.assertIsNone(response.json()["fecha_devolucion_pactada"])

    def test_blocked_user_cannot_request_or_join_waiting_list(self):
        self.user.estado = "BLOQUEADO"
        self.user.save(update_fields=["estado"])
        self.client.force_authenticate(user=self.user)

        request = self.client.post(
            reverse("loan_request"),
            {"libro": str(self.book.id), "biblioteca": str(self.library.id)},
            format="json",
        )
        waiting_list = self.client.post(reverse("waiting_list"), {"libro": str(self.book.id)}, format="json")

        self.assertEqual(request.status_code, 409)
        self.assertEqual(waiting_list.status_code, 409)

    def test_request_requires_library(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("loan_request"),
            {
                "libro": str(self.book.id),
                "fecha_devolucion_pactada": (timezone.now() + timedelta(days=14)).isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("biblioteca", response.json())

    def test_request_uses_copy_from_selected_library(self):
        other_librarian = CustomUser.objects.create_user(
            auth_uid="other-library-librarian",
            email="other-library-librarian@example.com",
            nombre="Luis",
            apellidos="Soto",
            ci="01020304064",
            tipo_usuario="BIBLIOTECARIO",
        )
        other_library = Biblioteca.objects.create(
            nombre="Facultad Técnica", direccion="Calle 2", responsable=other_librarian
        )
        other_copy = Ejemplar.objects.create(
            libro=self.book,
            biblioteca=other_library,
            codigo_ejemplar="LOAN-OTHER-001",
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("loan_request"),
            {
                "libro": str(self.book.id),
                "biblioteca": str(other_library.id),
                "fecha_devolucion_pactada": (timezone.now() + timedelta(days=14)).isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["biblioteca"], str(other_library.id))
        self.assertEqual(response.json()["ejemplar"], str(other_copy.id))

    def test_request_returns_conflict_when_no_copy_is_available(self):
        self.copy.estado = "PRESTADO"
        self.copy.save(update_fields=["estado"])
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("loan_request"),
            {
                "libro": str(self.book.id),
                "biblioteca": str(self.library.id),
                "fecha_devolucion_pactada": (timezone.now() + timedelta(days=14)).isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 409)

    def test_waiting_list_requires_all_copies_to_be_unavailable_and_is_idempotent(self):
        self.client.force_authenticate(user=self.user)
        available = self.client.post(
            reverse("waiting_list"), {"libro": str(self.book.id)}, format="json"
        )
        self.assertEqual(available.status_code, 409)

        self.copy.estado = "PRESTADO"
        self.copy.save(update_fields=["estado"])
        first = self.client.post(
            reverse("waiting_list"), {"libro": str(self.book.id)}, format="json"
        )
        duplicate = self.client.post(
            reverse("waiting_list"), {"libro": str(self.book.id)}, format="json"
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(ListaEspera.objects.filter(usuario=self.user, libro=self.book, estado="ACTIVA").count(), 1)

    def test_return_notifies_oldest_waiting_user_and_preserves_remaining_queue(self):
        second_user = CustomUser.objects.create_user(
            auth_uid="api-borrower-second",
            email="api-borrower-second@example.com",
            nombre="Luis",
            apellidos="Soto",
            ci="01020304064",
            tipo_usuario="ESTUDIANTE",
        )
        waiting_first = ListaEspera.objects.create(usuario=self.user, libro=self.book)
        waiting_second = ListaEspera.objects.create(usuario=second_user, libro=self.book)
        self.copy.estado = "PRESTADO"
        self.copy.save(update_fields=["estado"])
        loan = Prestamo.objects.create(
            usuario=CustomUser.objects.create_user(
                auth_uid="active-borrower",
                email="active-borrower@example.com",
                nombre="Eva",
                apellidos="Rios",
                ci="01020304065",
                tipo_usuario="TRABAJADOR",
            ),
            ejemplar=self.copy,
            biblioteca=self.library,
            fecha_devolucion_pactada=timezone.now() + timedelta(days=7),
            estado="ACTIVO",
        )
        librarian = CustomUser.objects.get(auth_uid="api-librarian")
        self._grant_librarian_permission(librarian, self.library)
        self.client.force_authenticate(user=librarian)

        response = self.client.post(reverse("loan_return", kwargs={"loan_id": str(loan.id)}))

        self.assertEqual(response.status_code, 200)
        waiting_first.refresh_from_db()
        waiting_second.refresh_from_db()
        self.assertEqual(waiting_first.estado, "NOTIFICADA")
        self.assertEqual(waiting_second.estado, "ACTIVA")
        notification = Notificacion.objects.get(usuario=self.user, tipo="DISPONIBILIDAD")
        self.assertIn(self.book.titulo, notification.mensaje)
        self.assertIn(self.library.nombre, notification.mensaje)
        self.assertFalse(Notificacion.objects.filter(usuario=second_user).exists())

    def test_waiting_list_is_private_and_requires_authentication(self):
        anonymous_response = self.client.post(
            reverse("waiting_list"), {"libro": str(self.book.id)}, format="json"
        )
        self.assertEqual(anonymous_response.status_code, 401)

        waiting = ListaEspera.objects.create(usuario=self.user, libro=self.book)
        other_user = CustomUser.objects.create_user(
            auth_uid="private-waiting-user",
            email="private-waiting@example.com",
            nombre="Other",
            apellidos="User",
            ci="01020304066",
            tipo_usuario="TRABAJADOR",
        )
        self.client.force_authenticate(user=other_user)
        response = self.client.get(reverse("waiting_list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])
        self.assertNotIn(str(waiting.id), str(response.json()))

    def test_user_can_request_renewal_for_own_active_loan(self):
        self.copy.estado = "PRESTADO"
        self.copy.save(update_fields=["estado"])
        loan = Prestamo.objects.create(
            usuario=self.user,
            ejemplar=self.copy,
            biblioteca=self.library,
            fecha_devolucion_pactada=timezone.now() + timedelta(days=3),
            estado="ACTIVO",
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.post(reverse("renewal_request", kwargs={"loan_id": str(loan.id)}), {}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["estado"], "PENDIENTE")

        loans = self.client.get(reverse("my_loans")).json()
        self.assertTrue(next(item for item in loans if item["id"] == str(loan.id))["renovacion_pendiente"])

    def test_renewal_is_blocked_by_pending_reservation_for_same_title(self):
        self.copy.estado = "PRESTADO"
        self.copy.save(update_fields=["estado"])
        loan = Prestamo.objects.create(
            usuario=self.user,
            ejemplar=self.copy,
            biblioteca=self.library,
            fecha_devolucion_pactada=timezone.now() + timedelta(days=3),
            estado="ACTIVO",
        )
        reserved_copy = Ejemplar.objects.create(
            libro=self.book,
            biblioteca=self.library,
            codigo_ejemplar="LOAN-RESERVED",
            estado="PRESTADO",
        )
        other_user = CustomUser.objects.create_user(
            auth_uid="renewal-reserver",
            email="renewal-reserver@example.com",
            nombre="Other",
            apellidos="User",
            ci="01020304067",
            tipo_usuario="TRABAJADOR",
        )
        Prestamo.objects.create(
            usuario=other_user,
            ejemplar=reserved_copy,
            biblioteca=self.library,
            estado="PENDIENTE",
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.post(reverse("renewal_request", kwargs={"loan_id": str(loan.id)}), {}, format="json")

        self.assertEqual(response.status_code, 409)
        self.assertIn("reservas", response.json()["detail"])
        self.assertFalse(RenovacionPrestamo.objects.exists())

    def test_librarian_approves_renewal_and_updates_due_date(self):
        self.copy.estado = "PRESTADO"
        self.copy.save(update_fields=["estado"])
        old_due_date = timezone.now() + timedelta(days=3)
        loan = Prestamo.objects.create(
            usuario=self.user,
            ejemplar=self.copy,
            biblioteca=self.library,
            fecha_devolucion_pactada=old_due_date,
            estado="ACTIVO",
        )
        self.client.force_authenticate(user=self.user)
        requested = self.client.post(
            reverse("renewal_request", kwargs={"loan_id": str(loan.id)}), {}, format="json"
        )
        renewal_id = requested.json()["id"]
        librarian = CustomUser.objects.get(auth_uid="api-librarian")
        self._grant_librarian_permission(librarian, self.library)
        self.client.force_authenticate(user=librarian)
        new_due_date = timezone.now() + timedelta(days=17)

        response = self.client.post(
            reverse("renewal_decide", kwargs={"renewal_id": renewal_id}),
            {"fecha_devolucion_pactada": new_due_date.isoformat()},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["estado"], "APROBADA")
        loan.refresh_from_db()
        self.assertEqual(loan.fecha_devolucion_pactada, new_due_date)
        self.assertTrue(Notificacion.objects.filter(usuario=self.user, tipo="RENOVACION_APROBADA").exists())

    def test_librarian_rechecks_reservations_before_approving_renewal(self):
        self.copy.estado = "PRESTADO"
        self.copy.save(update_fields=["estado"])
        loan = Prestamo.objects.create(
            usuario=self.user,
            ejemplar=self.copy,
            biblioteca=self.library,
            fecha_devolucion_pactada=timezone.now() + timedelta(days=3),
            estado="ACTIVO",
        )
        self.client.force_authenticate(user=self.user)
        requested = self.client.post(
            reverse("renewal_request", kwargs={"loan_id": str(loan.id)}), {}, format="json"
        )
        renewal_id = requested.json()["id"]
        reserved_copy = Ejemplar.objects.create(
            libro=self.book,
            biblioteca=self.library,
            codigo_ejemplar="LOAN-RESERVED-LATE",
            estado="PRESTADO",
        )
        other_user = CustomUser.objects.create_user(
            auth_uid="renewal-late-reserver",
            email="renewal-late-reserver@example.com",
            nombre="Other",
            apellidos="User",
            ci="01020304068",
            tipo_usuario="TRABAJADOR",
        )
        Prestamo.objects.create(
            usuario=other_user,
            ejemplar=reserved_copy,
            biblioteca=self.library,
            estado="LISTO",
        )
        librarian = CustomUser.objects.get(auth_uid="api-librarian")
        self._grant_librarian_permission(librarian, self.library)
        self.client.force_authenticate(user=librarian)

        response = self.client.post(
            reverse("renewal_decide", kwargs={"renewal_id": renewal_id}),
            {"fecha_devolucion_pactada": (timezone.now() + timedelta(days=17)).isoformat()},
            format="json",
        )

        self.assertEqual(response.status_code, 409)
        loan.refresh_from_db()
        self.assertEqual(loan.fecha_devolucion_pactada.date(), (timezone.now() + timedelta(days=3)).date())
        self.assertEqual(RenovacionPrestamo.objects.get(id=renewal_id).estado, "PENDIENTE")

    def test_librarian_can_reject_renewal_and_user_is_notified(self):
        self.copy.estado = "PRESTADO"
        self.copy.save(update_fields=["estado"])
        loan = Prestamo.objects.create(
            usuario=self.user,
            ejemplar=self.copy,
            biblioteca=self.library,
            fecha_devolucion_pactada=timezone.now() + timedelta(days=3),
            estado="ACTIVO",
        )
        self.client.force_authenticate(user=self.user)
        requested = self.client.post(
            reverse("renewal_request", kwargs={"loan_id": str(loan.id)}), {}, format="json"
        )
        librarian = CustomUser.objects.get(auth_uid="api-librarian")
        self._grant_librarian_permission(librarian, self.library)
        self.client.force_authenticate(user=librarian)

        response = self.client.post(
            reverse("renewal_decide", kwargs={"renewal_id": requested.json()["id"]}),
            {"motivo": "Existe una reserva pendiente."},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["estado"], "RECHAZADA")
        self.assertTrue(Notificacion.objects.filter(usuario=self.user, tipo="RENOVACION_RECHAZADA").exists())

    def test_renewal_queue_requires_librarian_permission(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse("renewal_queue"))

        self.assertEqual(response.status_code, 403)

    def test_request_requires_complete_profile(self):
        self.user.telefono = ""
        self.user.save(update_fields=["telefono"])
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("loan_request"),
            {
                "libro": str(self.book.id),
                "biblioteca": str(self.library.id),
                "fecha_devolucion_pactada": (timezone.now() + timedelta(days=14)).isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("perfil", response.json()["detail"])

    def test_librarian_finds_user_by_qr_id_and_ci(self):
        librarian = CustomUser.objects.get(auth_uid="api-librarian")
        from apps.rbac.models import Role, UserRole
        from django.core.management import call_command

        call_command("seed_roles", verbosity=0)
        UserRole.objects.create(
            user=librarian,
            role=Role.objects.get(name="bibliotecario"),
            resource_type="biblioteca",
            resource_id=str(librarian.biblioteca_id),
        )
        self.client.force_authenticate(user=librarian)

        by_id = self.client.get(reverse("user_lookup"), {"q": str(self.user.id)}).json()
        by_ci = self.client.get(reverse("user_lookup"), {"q": "01020304062"}).json()

        self.assertEqual([u["auth_uid"] for u in by_id], ["api-borrower"])
        self.assertEqual([u["auth_uid"] for u in by_ci], ["api-borrower"])

    def test_librarian_lookup_includes_borrowers_without_library_but_hides_other_staff(self):
        librarian = CustomUser.objects.get(auth_uid="api-librarian")
        other_librarian = CustomUser.objects.create_user(
            auth_uid="other-library-librarian",
            email="other-library-librarian@example.com",
            nombre="Other",
            apellidos="Librarian",
            ci="01020304080",
            tipo_usuario="BIBLIOTECARIO",
        )
        other_library = Biblioteca.objects.create(
            nombre="Otra sede",
            direccion="Calle 2",
            responsable=other_librarian,
        )
        other_librarian.biblioteca = other_library
        other_librarian.save(update_fields=["biblioteca"])
        from apps.rbac.models import Role, UserRole
        from django.core.management import call_command

        call_command("seed_roles", verbosity=0)
        librarian_role = Role.objects.get(name="bibliotecario")
        UserRole.objects.create(
            user=librarian,
            role=librarian_role,
            resource_type="biblioteca",
            resource_id=str(librarian.biblioteca_id),
        )
        UserRole.objects.create(
            user=other_librarian,
            role=librarian_role,
            resource_type="biblioteca",
            resource_id=str(other_library.id),
        )
        self.client.force_authenticate(user=librarian)

        response = self.client.get(reverse("user_lookup"), {"q": "api-"})
        auth_uids = {user["auth_uid"] for user in response.json()}

        self.assertEqual(response.status_code, 200)
        self.assertIn("api-borrower", auth_uids)
        self.assertNotIn("other-library-librarian", auth_uids)

    def test_duplicate_request_for_same_book_is_rejected(self):
        Ejemplar.objects.create(libro=self.book, biblioteca=self.library, codigo_ejemplar="LOAN-002")
        self.client.force_authenticate(user=self.user)
        payload = {
            "libro": str(self.book.id),
            "biblioteca": str(self.library.id),
        }

        first = self.client.post(reverse("loan_request"), payload, format="json")
        second = self.client.post(reverse("loan_request"), payload, format="json")

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 409)
        self.assertIn("Ya solicitaste", second.json()["detail"])
        self.assertEqual(self.user.prestamos.count(), 1)

    def test_librarian_completes_loan_lifecycle(self):
        self.client.force_authenticate(user=self.user)
        request_response = self.client.post(
            reverse("loan_request"),
            {
                "libro": str(self.book.id),
                "biblioteca": str(self.library.id),
            },
            format="json",
        )
        self.assertEqual(request_response.status_code, 201)
        self.assertIsNone(request_response.json()["fecha_devolucion_pactada"])
        loan_id = request_response.json()["id"]
        librarian = CustomUser.objects.get(auth_uid="api-librarian")
        self._grant_librarian_permission(librarian, self.library)
        self.client.force_authenticate(user=librarian)

        approve_response = self.client.post(
            reverse("loan_approve", kwargs={"loan_id": loan_id}),
            {"fecha_recogida_limite": (timezone.now() + timedelta(days=2)).isoformat()},
            format="json",
        )
        self.assertEqual(approve_response.status_code, 200)
        self.assertEqual(approve_response.json()["estado"], "LISTO")
        self.assertIsNone(approve_response.json()["fecha_devolucion_pactada"])
        approval_log = LogsAuditoria.objects.get(accion="LOAN_APPROVED", entidad="loan_approve")
        self.assertEqual(approval_log.entidad_id, loan_id)
        self.assertEqual(approval_log.datos_anteriores, {"estado": "PENDIENTE"})
        self.assertEqual(approval_log.datos_nuevos, {"estado": "LISTO"})

        collect_url = reverse("loan_collect", kwargs={"loan_id": loan_id})
        missing_date_response = self.client.post(collect_url, {}, format="json")
        self.assertEqual(missing_date_response.status_code, 400)

        past_date_response = self.client.post(
            collect_url,
            {"fecha_devolucion_pactada": (timezone.now() - timedelta(days=1)).isoformat()},
            format="json",
        )
        self.assertEqual(past_date_response.status_code, 409)

        due_date = timezone.now() + timedelta(days=14)
        collect_response = self.client.post(
            collect_url,
            {"fecha_devolucion_pactada": due_date.isoformat()},
            format="json",
        )
        self.assertEqual(collect_response.status_code, 200)
        self.assertEqual(collect_response.json()["estado"], "ACTIVO")
        self.assertIsNotNone(collect_response.json()["fecha_devolucion_pactada"])
        self.copy.refresh_from_db()
        self.assertEqual(self.copy.estado, "PRESTADO")

        return_response = self.client.post(reverse("loan_return", kwargs={"loan_id": loan_id}))
        self.assertEqual(return_response.status_code, 200)
        self.assertEqual(return_response.json()["estado"], "DEVUELTO")
        self.copy.refresh_from_db()
        self.assertEqual(self.copy.estado, "DISPONIBLE")

    def test_student_cannot_manage_loan(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            reverse("loan_approve", kwargs={"loan_id": "00000000-0000-0000-0000-000000000000"}),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_user_only_sees_own_loans_and_can_filter_by_status(self):
        own_loan = Prestamo.objects.create(
            usuario=self.user,
            ejemplar=self.copy,
            biblioteca=self.library,
            fecha_devolucion_pactada=timezone.now() + timedelta(days=10),
            estado="PENDIENTE",
        )
        other_user = CustomUser.objects.create_user(
            auth_uid="other-borrower",
            email="other@example.com",
            nombre="Other",
            apellidos="Borrower",
            ci="01020304064",
            tipo_usuario="ESTUDIANTE",
        )
        other_copy = Ejemplar.objects.create(
            libro=self.book,
            biblioteca=self.library,
            codigo_ejemplar="LOAN-002",
        )
        Prestamo.objects.create(
            usuario=other_user,
            ejemplar=other_copy,
            biblioteca=self.library,
            fecha_devolucion_pactada=timezone.now() + timedelta(days=10),
            estado="ACTIVO",
        )
        self.client.force_authenticate(user=self.user)

        all_response = self.client.get(reverse("my_loans"))
        pending_response = self.client.get(reverse("my_loans"), {"estado": "PENDIENTE"})

        self.assertEqual(all_response.status_code, 200)
        self.assertEqual(len(all_response.json()), 1)
        self.assertEqual(all_response.json()[0]["id"], str(own_loan.id))
        self.assertEqual(len(pending_response.json()), 1)

    def test_librarian_pending_queue_requires_rbac_permission(self):
        loan = Prestamo.objects.create(
            usuario=self.user,
            ejemplar=self.copy,
            biblioteca=self.library,
            fecha_devolucion_pactada=timezone.now() + timedelta(days=10),
            estado="PENDIENTE",
        )

        self.client.force_authenticate(user=self.user)
        denied = self.client.get(reverse("pending_loans"))
        self.assertEqual(denied.status_code, 403)

        librarian = CustomUser.objects.get(auth_uid="api-librarian")
        self._grant_librarian_permission(librarian, self.library)
        self.client.force_authenticate(user=librarian)

        allowed = self.client.get(reverse("pending_loans"))
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual([item["id"] for item in allowed.json()], [str(loan.id)])
        self.assertEqual(allowed.json()[0]["usuario_nombre"], "Ana Perez")

    def test_librarian_cannot_see_or_manage_loans_from_another_library(self):
        other_library = Biblioteca.objects.create(
            nombre="Tecnica", direccion="Calle 2", responsable=self.library.responsable
        )
        other_copy = Ejemplar.objects.create(
            libro=self.book,
            biblioteca=other_library,
            codigo_ejemplar="LOAN-OTHER-LIBRARY",
        )
        other_loan = Prestamo.objects.create(
            usuario=self.user,
            ejemplar=other_copy,
            biblioteca=other_library,
            fecha_devolucion_pactada=timezone.now() + timedelta(days=10),
            estado="PENDIENTE",
        )
        librarian = CustomUser.objects.get(auth_uid="api-librarian")
        self._grant_librarian_permission(librarian, self.library)
        self.client.force_authenticate(user=librarian)

        pending = self.client.get(reverse("pending_loans"))
        action = self.client.post(
            reverse("loan_approve", kwargs={"loan_id": str(other_loan.id)}),
            {},
            format="json",
        )

        self.assertEqual(pending.status_code, 200)
        self.assertNotIn(str(other_loan.id), [item["id"] for item in pending.json()])
        self.assertEqual(action.status_code, 409)
        other_loan.refresh_from_db()
        self.assertEqual(other_loan.estado, "PENDIENTE")

    def test_librarian_can_register_counter_loan(self):
        librarian = CustomUser.objects.get(auth_uid="api-librarian")
        self._grant_librarian_permission(librarian, self.library)
        self.client.force_authenticate(user=librarian)

        response = self.client.post(
            reverse("counter_loan"),
            {
                "usuario": str(self.user.id),
                "libro": str(self.book.id),
                "biblioteca": str(self.library.id),
                "fecha_devolucion_pactada": (timezone.now() + timedelta(days=14)).isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["estado"], "ACTIVO")
        self.assertEqual(response.json()["bibliotecario"], str(librarian.id))
        self.copy.refresh_from_db()
        self.assertEqual(self.copy.estado, "PRESTADO")

    @staticmethod
    def _grant_librarian_permission(user, library=None):
        from apps.rbac.models import Permission, Role, RolePermission, UserRole

        role = Role.objects.create(name="test-bibliotecario", display_name="Bibliotecario")
        permission = Permission.objects.create(name="prestamos.manage")
        RolePermission.objects.create(role=role, permission=permission)
        UserRole.objects.create(
            user=user,
            role=role,
            resource_type="biblioteca" if library else None,
            resource_id=str(library.id) if library else None,
        )


class DueDateNotificationTests(APITestCase):
    def setUp(self):
        from django.core.management import call_command

        from apps.rbac.models import Role, UserRole

        self.user = CustomUser.objects.create_user(
            auth_uid="due-user", email="due@example.com", nombre="Eva", apellidos="Rios",
            ci="01020304071", telefono="55512345", tipo_usuario="TRABAJADOR",
        )
        self.librarian = CustomUser.objects.create_user(
            auth_uid="due-librarian", email="dl@example.com", nombre="Luis", apellidos="Paz",
            ci="01020304072", tipo_usuario="BIBLIOTECARIO",
        )
        call_command("seed_roles", verbosity=0)
        library = Biblioteca.objects.create(nombre="Central", direccion="Calle 1", responsable=self.librarian)
        self.librarian.biblioteca = library
        self.librarian.save(update_fields=["biblioteca"])
        UserRole.objects.create(
            user=self.librarian,
            role=Role.objects.get(name="bibliotecario"),
            resource_type="biblioteca",
            resource_id=str(library.id),
        )
        publisher = Editorial.objects.create(nombre="Editorial UHO")
        self.book = Libro.objects.create(titulo="Libro con plazo", editorial=publisher)
        self.library = library
        self.counter = 0

    def _loan(self, days):
        self.counter += 1
        copy = Ejemplar.objects.create(
            libro=self.book, biblioteca=self.library, codigo_ejemplar=f"DUE-{self.counter}", estado="PRESTADO"
        )
        return Prestamo.objects.create(
            usuario=self.user, ejemplar=copy, biblioteca=self.library, estado="ACTIVO",
            fecha_devolucion_pactada=timezone.now() + timedelta(days=days),
        )

    def test_notifies_three_days_before_and_day_after_due_once(self):
        from .vencimientos import notify_due_loans

        soon = self._loan(3)
        late = self._loan(-1)
        far = self._loan(10)

        first = notify_due_loans()
        second = notify_due_loans()

        self.assertEqual(first, {"por_vencer": 1, "vencidos": 1})
        self.assertEqual(second, {"por_vencer": 0, "vencidos": 0})
        self.assertTrue(Notificacion.objects.filter(prestamo=soon, tipo="POR_VENCER", usuario=self.user).exists())
        self.assertTrue(Notificacion.objects.filter(prestamo=late, tipo="VENCIDO", usuario=self.user).exists())
        self.assertFalse(Notificacion.objects.filter(prestamo=far).exists())

    def test_user_sees_and_marks_notifications_in_app(self):
        self._loan(2)
        self.client.force_authenticate(user=self.user)

        listing = self.client.get(reverse("my_notifications")).json()
        self.assertEqual(len(listing), 1)
        self.assertFalse(listing[0]["leida"])

        read = self.client.post(reverse("notification_read", kwargs={"notification_id": listing[0]["id"]}))
        self.assertEqual(read.json()["actualizadas"], 1)
        self.assertTrue(self.client.get(reverse("my_notifications")).json()[0]["leida"])

    def test_librarian_sees_upcoming_and_overdue_loans(self):
        soon = self._loan(2)
        late = self._loan(-2)
        self._loan(10)
        self.client.force_authenticate(user=self.librarian)

        data = self.client.get(reverse("due_loans")).json()

        self.assertEqual([l["id"] for l in data["proximos"]], [str(soon.id)])
        self.assertEqual([l["id"] for l in data["vencidos"]], [str(late.id)])
        self.assertTrue(data["vencidos"][0]["vencido"])
        self.assertEqual(data["proximos"][0]["dias_restantes"], 2)

    def test_regular_user_cannot_see_due_loans_panel_data(self):
        self.client.force_authenticate(user=self.user)
        self.assertEqual(self.client.get(reverse("due_loans")).status_code, 403)


class SanctionApiTests(APITestCase):
    def setUp(self):
        DueDateNotificationTests.setUp(self)

    def _loan(self, days):
        copy = Ejemplar.objects.create(
            libro=self.book,
            biblioteca=self.library,
            codigo_ejemplar=f"SANCTION-{Prestamo.objects.count() + 1}",
            estado="PRESTADO",
        )
        return Prestamo.objects.create(
            usuario=self.user,
            ejemplar=copy,
            biblioteca=self.library,
            estado="ACTIVO",
            fecha_devolucion_pactada=timezone.now() + timedelta(days=days),
        )

    def test_librarian_can_sanction_overdue_user_and_unblock_them(self):
        loan = self._loan(-2)
        self.client.force_authenticate(user=self.librarian)

        listed = self.client.get(reverse("sanctions"))
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([item["id"] for item in listed.json()["vencidos"]], [str(loan.id)])

        created = self.client.post(reverse("sanctions"), {"prestamo": str(loan.id), "motivo": "Préstamo vencido"}, format="json")
        self.assertEqual(created.status_code, 201)
        self.user.refresh_from_db()
        self.assertEqual(self.user.estado, "BLOQUEADO")
        self.assertTrue(Sancion.objects.get(id=created.json()["id"]).activa)
        self.assertTrue(Notificacion.objects.filter(usuario=self.user, tipo="SANCION").exists())

        active = self.client.get(reverse("sanctions")).json()["sancionados"]
        self.assertEqual(len(active), 1)
        unblocked = self.client.post(reverse("sanction_unblock", kwargs={"sanction_id": created.json()["id"]}))
        self.assertEqual(unblocked.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.estado, "ACTIVO")
        self.assertFalse(Sancion.objects.get(id=created.json()["id"]).activa)
        self.assertTrue(Notificacion.objects.filter(usuario=self.user, tipo="DESBLOQUEO").exists())

    def test_cannot_sanction_non_overdue_loan_or_from_another_library(self):
        loan = self._loan(2)
        other_library = Biblioteca.objects.create(nombre="Tecnica", direccion="Calle 2", responsable=self.librarian)
        other_copy = Ejemplar.objects.create(
            libro=self.book, biblioteca=other_library, codigo_ejemplar="SANCTION-OTHER", estado="PRESTADO"
        )
        other_loan = Prestamo.objects.create(
            usuario=self.user,
            ejemplar=other_copy,
            biblioteca=other_library,
            estado="ACTIVO",
            fecha_devolucion_pactada=timezone.now() - timedelta(days=1),
        )
        self.client.force_authenticate(user=self.librarian)

        not_due = self.client.post(reverse("sanctions"), {"prestamo": str(loan.id)}, format="json")
        wrong_library = self.client.post(reverse("sanctions"), {"prestamo": str(other_loan.id)}, format="json")

        self.assertEqual(not_due.status_code, 409)
        self.assertEqual(wrong_library.status_code, 403)
        self.assertFalse(Sancion.objects.exists())

    def test_due_today_loan_is_not_yet_sanctionable(self):
        start_today, _ = due_windows()
        copy = Ejemplar.objects.create(
            libro=self.book, biblioteca=self.library, codigo_ejemplar="SANCTION-TODAY", estado="PRESTADO"
        )
        loan = Prestamo.objects.create(
            usuario=self.user,
            ejemplar=copy,
            biblioteca=self.library,
            estado="ACTIVO",
            fecha_devolucion_pactada=start_today,
        )
        self.client.force_authenticate(user=self.librarian)

        response = self.client.post(reverse("sanctions"), {"prestamo": str(loan.id)}, format="json")

        self.assertEqual(response.status_code, 409)

    def test_regular_user_cannot_manage_sanctions(self):
        self.client.force_authenticate(user=self.user)
        self.assertEqual(self.client.get(reverse("sanctions")).status_code, 403)

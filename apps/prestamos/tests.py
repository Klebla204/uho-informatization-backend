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

from .models import Carnet, ListaEspera, Notificacion, Prestamo


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
                "fecha_devolucion_pactada": (timezone.now() + timedelta(days=14)).isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["estado"], "PENDIENTE")
        self.assertIsNone(response.json()["bibliotecario"])

    def test_request_returns_conflict_when_no_copy_is_available(self):
        self.copy.estado = "PRESTADO"
        self.copy.save(update_fields=["estado"])
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("loan_request"),
            {
                "libro": str(self.book.id),
                "fecha_devolucion_pactada": (timezone.now() + timedelta(days=14)).isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 409)

    def test_request_requires_complete_profile(self):
        self.user.telefono = ""
        self.user.save(update_fields=["telefono"])
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("loan_request"),
            {
                "libro": str(self.book.id),
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
        UserRole.objects.create(user=librarian, role=Role.objects.get(name="bibliotecario"))
        self.client.force_authenticate(user=librarian)

        by_id = self.client.get(reverse("user_lookup"), {"q": str(self.user.id)}).json()
        by_ci = self.client.get(reverse("user_lookup"), {"q": "01020304062"}).json()

        self.assertEqual([u["auth_uid"] for u in by_id], ["api-borrower"])
        self.assertEqual([u["auth_uid"] for u in by_ci], ["api-borrower"])

    def test_duplicate_request_for_same_book_is_rejected(self):
        Ejemplar.objects.create(libro=self.book, biblioteca=self.library, codigo_ejemplar="LOAN-002")
        self.client.force_authenticate(user=self.user)
        payload = {
            "libro": str(self.book.id),
            "fecha_devolucion_pactada": (timezone.now() + timedelta(days=14)).isoformat(),
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
                "fecha_devolucion_pactada": (timezone.now() + timedelta(days=14)).isoformat(),
            },
            format="json",
        )
        self.assertEqual(request_response.status_code, 201)
        loan_id = request_response.json()["id"]
        librarian = CustomUser.objects.get(auth_uid="api-librarian")
        self._grant_librarian_permission(librarian)
        self.client.force_authenticate(user=librarian)

        approve_response = self.client.post(
            reverse("loan_approve", kwargs={"loan_id": loan_id}),
            {"fecha_recogida_limite": (timezone.now() + timedelta(days=2)).isoformat()},
            format="json",
        )
        self.assertEqual(approve_response.status_code, 200)
        self.assertEqual(approve_response.json()["estado"], "LISTO")

        collect_response = self.client.post(reverse("loan_collect", kwargs={"loan_id": loan_id}))
        self.assertEqual(collect_response.status_code, 200)
        self.assertEqual(collect_response.json()["estado"], "ACTIVO")
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
        self._grant_librarian_permission(librarian)
        self.client.force_authenticate(user=librarian)

        allowed = self.client.get(reverse("pending_loans"))
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual([item["id"] for item in allowed.json()], [str(loan.id)])
        self.assertEqual(allowed.json()[0]["usuario_nombre"], "Ana Perez")

    def test_librarian_can_register_counter_loan(self):
        librarian = CustomUser.objects.get(auth_uid="api-librarian")
        self._grant_librarian_permission(librarian)
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
    def _grant_librarian_permission(user):
        from apps.rbac.models import Permission, Role, RolePermission, UserRole

        role = Role.objects.create(name="test-bibliotecario", display_name="Bibliotecario")
        permission = Permission.objects.create(name="prestamos.manage")
        RolePermission.objects.create(role=role, permission=permission)
        UserRole.objects.create(user=user, role=role)


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
        UserRole.objects.create(user=self.librarian, role=Role.objects.get(name="bibliotecario"))
        library = Biblioteca.objects.create(nombre="Central", direccion="Calle 1", responsable=self.librarian)
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

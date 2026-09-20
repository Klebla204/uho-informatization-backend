from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from django.utils import timezone

from apps.catalogo.models import Autor, Biblioteca, Categoria, Editorial, Ejemplar, Libro
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
            tipo_usuario="ESTUDIANTE",
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
        loan_id = request_response.json()["id"]
        librarian = CustomUser.objects.get(auth_uid="api-librarian")
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

        self.assertEqual(response.status_code, 409)

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
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

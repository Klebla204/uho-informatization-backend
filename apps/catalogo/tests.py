from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.users.models import CustomUser

from .models import Autor, Biblioteca, Categoria, Editorial, Ejemplar, Libro


class LibraryModelTests(TestCase):
    def test_library_has_uuid_and_responsible_user(self):
        user = CustomUser.objects.create_user(
            auth_uid="librarian-1",
            email="librarian@example.com",
            nombre="Marta",
            apellidos="Diaz",
            ci="01020304052",
            tipo_usuario="BIBLIOTECARIO",
        )
        library = Biblioteca.objects.create(
            nombre="Biblioteca Central",
            facultad_asociada="Universidad de Holguin",
            direccion="Avenida Principal",
            telefono="5550000",
            responsable=user,
        )

        self.assertIsNotNone(library.id)
        self.assertEqual(library.responsable, user)
        self.assertTrue(library.activa)

    def test_book_connects_authors_categories_and_library_copies(self):
        user = CustomUser.objects.create_user(
            auth_uid="librarian-2",
            email="librarian2@example.com",
            nombre="Carlos",
            apellidos="Ruiz",
            ci="01020304053",
            tipo_usuario="BIBLIOTECARIO",
        )
        library = Biblioteca.objects.create(
            nombre="Biblioteca de Ingenieria",
            direccion="Calle 1",
            responsable=user,
        )
        author = Autor.objects.create(nombre="Luis", apellidos="Joyanes Aguilar")
        category = Categoria.objects.create(nombre="Programacion")
        publisher = Editorial.objects.create(nombre="Alfaomega", pais="Mexico")
        book = Libro.objects.create(
            titulo="Fundamentos de Programacion",
            isbn="9788441537461",
            anio_edicion=2019,
            editorial=publisher,
            edicion="7ma",
        )
        book.autores.add(author)
        book.categorias.add(category)
        copy = Ejemplar.objects.create(
            libro=book,
            biblioteca=library,
            codigo_ejemplar="ING-0001",
            ubicacion_fisica="Estante A, Seccion 2",
        )

        self.assertEqual(book.autores.get(), author)
        self.assertEqual(book.categorias.get(), category)
        self.assertEqual(book.ejemplares.get(), copy)
        self.assertEqual(copy.estado, "DISPONIBLE")


class CatalogApiTests(APITestCase):
    def setUp(self):
        user = CustomUser.objects.create_user(
            auth_uid="api-librarian",
            email="api-librarian@example.com",
            nombre="Marta",
            apellidos="Diaz",
            ci="01020304054",
            tipo_usuario="BIBLIOTECARIO",
        )
        library = Biblioteca.objects.create(nombre="Central", direccion="Calle 1", responsable=user)
        publisher = Editorial.objects.create(nombre="Editorial UHO")
        author = Autor.objects.create(nombre="Ana", apellidos="Gonzalez")
        category = Categoria.objects.create(nombre="Ciencias")
        self.book = Libro.objects.create(titulo="Ciencias para todos", editorial=publisher)
        self.book.autores.add(author)
        self.book.categorias.add(category)
        Ejemplar.objects.create(libro=self.book, biblioteca=library, codigo_ejemplar="API-001")

    def test_public_catalog_lists_available_book(self):
        response = self.client.get(
            reverse("libro_list"),
            {"q": "ciencias", "disponibilidad": "disponible"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["titulo"], "Ciencias para todos")
        self.assertEqual(response.json()[0]["ejemplares_disponibles"], 1)

    def test_book_detail_includes_copies_and_is_public(self):
        response = self.client.get(reverse("libro_detail", kwargs={"libro_id": self.book.id}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], str(self.book.id))
        self.assertEqual(len(response.json()["ejemplares"]), 1)

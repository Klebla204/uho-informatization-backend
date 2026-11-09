from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from io import BytesIO
from openpyxl import Workbook

from apps.users.models import CustomUser
from apps.rbac.models import Permission, Role, RolePermission, UserRole

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

    def test_public_libraries_endpoint_lists_only_active_libraries(self):
        librarian = Biblioteca.objects.get(nombre="Central").responsable
        Biblioteca.objects.create(nombre="Inactiva", direccion="Calle 2", responsable=librarian, activa=False)

        response = self.client.get(reverse("biblioteca_list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["nombre"] for item in response.json()], ["Central"])

    def test_public_categories_endpoint_lists_only_active_categories(self):
        inactive = Categoria.objects.create(nombre="Inactiva", activa=False)

        response = self.client.get(reverse("categoria_list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["nombre"] for item in response.json()], ["Ciencias"])
        self.assertNotIn(str(inactive.id), [item["id"] for item in response.json()])

    def test_catalog_crud_requires_catalog_manage_permission(self):
        user = CustomUser.objects.create_user(
            auth_uid="catalog-reader",
            email="reader@example.com",
            nombre="Reader",
            apellidos="User",
            ci="01020304055",
            tipo_usuario="ESTUDIANTE",
        )
        self.client.force_authenticate(user=user)

        response = self.client.post(
            "/api/v1/admin/catalogo/autores/",
            {"nombre": "Autor", "apellidos": "No autorizado"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_catalog_manager_can_create_author(self):
        user = CustomUser.objects.create_user(
            auth_uid="catalog-manager",
            email="manager@example.com",
            nombre="Catalog",
            apellidos="Manager",
            ci="01020304056",
            tipo_usuario="BIBLIOTECARIO",
        )
        role = Role.objects.create(name="bibliotecario", display_name="Bibliotecario")
        permission = Permission.objects.create(name="catalogo.manage")
        RolePermission.objects.create(role=role, permission=permission)
        UserRole.objects.create(user=user, role=role)
        self.client.force_authenticate(user=user)

        response = self.client.post(
            "/api/v1/admin/catalogo/autores/",
            {"nombre": "Autor", "apellidos": "Bibliotecario"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["apellidos"], "Bibliotecario")

    def test_deleting_book_archives_it_and_keeps_copies(self):
        user = CustomUser.objects.create_user(
            auth_uid="catalog-archiver",
            email="archiver@example.com",
            nombre="Catalog",
            apellidos="Archiver",
            ci="01020304057",
            tipo_usuario="BIBLIOTECARIO",
        )
        role = Role.objects.create(name="catalog-archiver", display_name="Catalog Archiver")
        permission = Permission.objects.create(name="catalogo.manage")
        RolePermission.objects.create(role=role, permission=permission)
        UserRole.objects.create(user=user, role=role)
        self.client.force_authenticate(user=user)

        response = self.client.delete(f"/api/v1/admin/catalogo/libros/{self.book.id}/")

        self.assertEqual(response.status_code, 204)
        self.book.refresh_from_db()
        self.assertFalse(self.book.activo)
        self.assertEqual(self.book.ejemplares.count(), 1)
        self.assertEqual(self.client.get(reverse("libro_list")).json(), [])

    def test_copy_crud_can_filter_by_book(self):
        user = CustomUser.objects.create_user(
            auth_uid="copy-reader",
            email="copy-reader@example.com",
            nombre="Copy",
            apellidos="Reader",
            ci="01020304058",
            tipo_usuario="BIBLIOTECARIO",
        )
        role = Role.objects.create(name="copy-reader", display_name="Copy Reader")
        permission = Permission.objects.create(name="catalogo.view")
        RolePermission.objects.create(role=role, permission=permission)
        UserRole.objects.create(user=user, role=role)
        self.client.force_authenticate(user=user)

        response = self.client.get(
            f"/api/v1/admin/catalogo/ejemplares/?libro={self.book.id}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["libro"], str(self.book.id))

    def test_collection_import_creates_book_and_exemplars(self):
        from apps.catalogo.import_services import import_collection

        workbook = Workbook()
        sheet = workbook.active
        sheet.append([
            "titulo", "isbn", "autor_principal", "otros_autores", "editorial",
            "año_edicion", "edicion", "categoria", "subcategoria", "resumen",
            "portada_url", "biblioteca", "cantidad_ejemplares", "ubicacion_fisica", "activo",
        ])
        sheet.append([
            "Libro importado", "9780000000001", "Perez, Ana", "", "Editorial UHO",
            2020, "1ra", "Ciencias", "", "Resumen", "", "Central", 2, "Estante A", "SI",
        ])
        file_object = BytesIO()
        workbook.save(file_object)
        file_object.seek(0)

        from apps.catalogo.import_services import import_collection
        result = import_collection(file_object)

        self.assertEqual(result.processed, 1)
        self.assertEqual(result.created, 1)
        self.assertEqual(result.copies_created, 2)
        self.assertEqual(result.errors, [])
        self.assertEqual(Libro.objects.get(isbn="9780000000001").ejemplares.count(), 2)

    def test_collection_import_reports_invalid_rows_without_stopping(self):
        from apps.catalogo.import_services import import_collection

        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["titulo", "isbn", "autor_principal", "editorial", "año_edicion", "categoria", "biblioteca", "cantidad_ejemplares", "activo"])
        sheet.append(["Valido", "9780000000002", "Perez, Ana", "Editorial UHO", 2020, "Ciencias", "Central", 1, "SI"])
        sheet.append(["Invalido", "9780000000003", "Autor sin formato", "Editorial UHO", 2020, "Ciencias", "Central", 1, "SI"])
        file_object = BytesIO()
        workbook.save(file_object)
        file_object.seek(0)

        from apps.catalogo.import_services import import_collection
        result = import_collection(file_object)

        self.assertEqual(result.processed, 2)
        self.assertEqual(result.created, 1)
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(Libro.objects.filter(isbn="9780000000002").count(), 1)

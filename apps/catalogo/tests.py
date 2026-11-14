from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase
from io import BytesIO
from openpyxl import Workbook

from apps.users.models import CustomUser
from apps.rbac.models import Permission, Role, RolePermission, UserRole

from .models import Autor, Biblioteca, Categoria, Editorial, Ejemplar, Libro


class LibraryModelTests(TestCase):
    def test_seed_libraries_creates_four_sedes_idempotently(self):
        from django.core.management import call_command

        user = CustomUser.objects.create_user(
            auth_uid="library-seed-admin",
            email="library-seed-admin@example.com",
            nombre="Super",
            apellidos="Administrador",
            ci="LIBRARY-SEED-ADMIN",
            tipo_usuario="SUPER_ADMIN",
        )

        call_command("seed_libraries", responsable_id=str(user.id), verbosity=0)
        call_command("seed_libraries", responsable_id=str(user.id), verbosity=0)

        names = {
            "Sede Oscar Lucero",
            "Sede Manuel Fajardo",
            "Sede Jose de la Luz y Caballero",
            "Sede Celia Sánchez",
        }
        libraries = Biblioteca.objects.filter(nombre__in=names)
        self.assertEqual(libraries.count(), 4)
        self.assertEqual(set(libraries.values_list("nombre", flat=True)), names)
        self.assertEqual(set(libraries.values_list("responsable_id", flat=True)), {user.id})
        self.assertEqual(set(libraries.values_list("direccion", flat=True)), {"Por definir"})

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
        self.library = Biblioteca.objects.create(nombre="Central", direccion="Calle 1", responsable=user)
        user.biblioteca = self.library
        user.save(update_fields=["biblioteca"])
        publisher = Editorial.objects.create(nombre="Editorial UHO")
        author = Autor.objects.create(nombre="Ana", apellidos="Gonzalez")
        category = Categoria.objects.create(nombre="Ciencias")
        self.book = Libro.objects.create(titulo="Ciencias para todos", editorial=publisher)
        self.book.autores.add(author)
        self.book.categorias.add(category)
        Ejemplar.objects.create(libro=self.book, biblioteca=self.library, codigo_ejemplar="API-001")

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

    def test_openapi_30_documents_public_availability_and_jwt_loans(self):
        response = self.client.get("/api/schema/", HTTP_ACCEPT="application/json")

        self.assertEqual(response.status_code, 200)
        schema = response.json()
        self.assertEqual(schema["openapi"], "3.0.3")
        self.assertIn("/api/v1/libros/", schema["paths"])
        self.assertIn("/api/v1/libros/{libro_id}/", schema["paths"])
        self.assertIn("/api/v1/prestamos/mis-prestamos/", schema["paths"])
        self.assertIn("jwtAuth", schema["components"]["securitySchemes"])
        loan_operation = schema["paths"]["/api/v1/prestamos/mis-prestamos/"]["get"]
        self.assertIn({"jwtAuth": []}, loan_operation["security"])
        schemas = schema["components"]["schemas"]
        self.assertIn("ejemplares_disponibles", schemas["LibroList"]["properties"])
        self.assertIn("ejemplares", schemas["LibroDetail"]["properties"])
        self.assertIn("disponible", schemas["Ejemplar"]["properties"])

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
        user.biblioteca = self.library
        user.save(update_fields=["biblioteca"])
        UserRole.objects.create(user=user, role=role, resource_type="biblioteca", resource_id=str(self.library.id))
        self.client.force_authenticate(user=user)

        response = self.client.post(
            "/api/v1/admin/catalogo/autores/",
            {"nombre": "Autor", "apellidos": "Bibliotecario"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["apellidos"], "Bibliotecario")

    def test_librarian_creates_book_with_initial_copies_at_own_library(self):
        user = CustomUser.objects.create_user(
            auth_uid="catalog-book-manager",
            email="book-manager@example.com",
            nombre="Catalog",
            apellidos="Book Manager",
            ci="01020304081",
            tipo_usuario="BIBLIOTECARIO",
            biblioteca=self.library,
        )
        role = Role.objects.create(name="catalog-book-manager")
        permission = Permission.objects.create(name="catalogo.manage")
        RolePermission.objects.create(role=role, permission=permission)
        UserRole.objects.create(
            user=user,
            role=role,
            resource_type="biblioteca",
            resource_id=str(self.library.id),
        )
        self.client.force_authenticate(user=user)

        payload = {
            "titulo": "Libro con inventario inicial",
            "editorial": str(self.book.editorial_id),
            "autores": [str(self.book.autores.first().id)],
            "categorias": [str(self.book.categorias.first().id)],
            "activo": True,
        }
        empty_stock_response = self.client.post(
            "/api/v1/admin/catalogo/libros/",
            {**payload, "cantidad_ejemplares": 0},
            format="json",
        )
        self.assertEqual(empty_stock_response.status_code, 400)
        self.assertFalse(Libro.objects.filter(titulo=payload["titulo"]).exists())

        response = self.client.post(
            "/api/v1/admin/catalogo/libros/",
            {**payload, "cantidad_ejemplares": 3},
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.json())
        created_book = Libro.objects.get(titulo="Libro con inventario inicial")
        copies = created_book.ejemplares.all()
        self.assertEqual(copies.count(), 3)
        self.assertEqual(set(copies.values_list("biblioteca_id", flat=True)), {self.library.id})
        public_response = self.client.get(
            reverse("libro_list"),
            {"q": "Libro con inventario inicial", "disponibilidad": "disponible"},
        )
        self.assertEqual(public_response.status_code, 200)
        self.assertEqual(public_response.json()[0]["ejemplares_disponibles"], 3)

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
        user.biblioteca = self.book.ejemplares.first().biblioteca
        user.save(update_fields=["biblioteca"])
        UserRole.objects.create(user=user, role=role, resource_type="biblioteca", resource_id=str(user.biblioteca_id))
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
        user.biblioteca = self.book.ejemplares.first().biblioteca
        user.save(update_fields=["biblioteca"])
        UserRole.objects.create(user=user, role=role, resource_type="biblioteca", resource_id=str(user.biblioteca_id))
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
        self.assertEqual(result.errors[0]["fila"], 3)
        self.assertEqual(Libro.objects.filter(isbn="9780000000002").count(), 1)

    def test_collection_import_updates_title_and_reconciles_copy_count(self):
        from apps.catalogo.import_services import import_collection

        def make_file(title, count):
            workbook = Workbook()
            sheet = workbook.active
            sheet.append([
                "titulo", "isbn", "autor_principal", "editorial", "año_edicion",
                "categoria", "biblioteca", "cantidad_ejemplares", "activo",
            ])
            sheet.append([title, "9780000000004", "Perez, Ana", "Editorial UHO", 2020,
                          "Ciencias", "Central", count, "SI"])
            file_object = BytesIO()
            workbook.save(file_object)
            file_object.seek(0)
            return file_object

        created = import_collection(make_file("Primera versión", 2))
        updated = import_collection(make_file("Título actualizado", 1))
        book = Libro.objects.get(isbn="9780000000004")

        self.assertEqual(created.created, 1)
        self.assertEqual(created.copies_created, 2)
        self.assertEqual(updated.updated, 1)
        self.assertEqual(updated.copies_created, 0)
        self.assertEqual(updated.copies_archived, 1)
        self.assertEqual(book.titulo, "Título actualizado")
        self.assertEqual(book.ejemplares.filter(estado="BAJA").count(), 1)
        self.assertEqual(book.ejemplares.exclude(estado="BAJA").count(), 1)

    def test_collection_template_contains_required_headers(self):
        from openpyxl import load_workbook
        from apps.catalogo.import_services import REQUIRED_COLUMNS, build_collection_template

        workbook = load_workbook(BytesIO(build_collection_template()), read_only=True)
        headers = set(next(workbook["Libros"].iter_rows(values_only=True)))

        self.assertTrue(REQUIRED_COLUMNS.issubset(headers))
        self.assertIn("Instrucciones", workbook.sheetnames)

    def test_collection_template_endpoint_returns_xlsx(self):
        from openpyxl import load_workbook

        user = CustomUser.objects.create_user(
            auth_uid="import-template-admin",
            email="import-template@example.com",
            nombre="Import",
            apellidos="Admin",
            ci="01020304059",
            tipo_usuario="ADMINISTRADOR",
        )
        user.biblioteca = self.library
        user.save(update_fields=["biblioteca"])
        role = Role.objects.create(name="import-template-admin")
        permission = Permission.objects.create(name="catalogo.manage")
        RolePermission.objects.create(role=role, permission=permission)
        UserRole.objects.create(
            user=user,
            role=role,
            resource_type="biblioteca",
            resource_id=str(self.library.id),
        )
        self.client.force_authenticate(user=user)

        response = self.client.get("/api/v1/admin/catalogo/plantilla/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("spreadsheetml.sheet", response["Content-Type"])
        workbook = load_workbook(BytesIO(b"".join(response.streaming_content)), read_only=True)
        self.assertIn("Instrucciones", workbook.sheetnames)

    def test_collection_import_endpoint_rejects_non_xlsx(self):
        user = CustomUser.objects.create_user(
            auth_uid="import-file-admin",
            email="import-file@example.com",
            nombre="Import",
            apellidos="Admin",
            ci="01020304060",
            tipo_usuario="ADMINISTRADOR",
        )
        user.biblioteca = self.library
        user.save(update_fields=["biblioteca"])
        role = Role.objects.create(name="import-file-admin")
        permission = Permission.objects.create(name="catalogo.manage")
        RolePermission.objects.create(role=role, permission=permission)
        UserRole.objects.create(
            user=user,
            role=role,
            resource_type="biblioteca",
            resource_id=str(self.library.id),
        )
        self.client.force_authenticate(user=user)

        response = self.client.post(
            "/api/v1/admin/catalogo/importar/",
            {"file": BytesIO(b"not an excel workbook")},
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(".xlsx", response.json()["detail"])

    def test_collection_import_endpoint_accepts_xlsx_upload(self):
        user = CustomUser.objects.create_user(
            auth_uid="import-upload-admin",
            email="import-upload@example.com",
            nombre="Import",
            apellidos="Admin",
            ci="01020304061",
            tipo_usuario="ADMINISTRADOR",
        )
        user.biblioteca = self.library
        user.save(update_fields=["biblioteca"])
        role = Role.objects.create(name="import-upload-admin")
        permission = Permission.objects.create(name="catalogo.manage")
        RolePermission.objects.create(role=role, permission=permission)
        UserRole.objects.create(
            user=user,
            role=role,
            resource_type="biblioteca",
            resource_id=str(self.library.id),
        )
        self.client.force_authenticate(user=user)

        workbook = Workbook()
        sheet = workbook.active
        sheet.append([
            "titulo", "isbn", "autor_principal", "editorial", "año_edicion",
            "categoria", "biblioteca", "cantidad_ejemplares", "activo",
        ])
        sheet.append([
            "Carga HTTP", "9780000000005", "Perez, Ana", "Editorial UHO", 2020,
            "Ciencias", "Central", 1, "SI",
        ])
        output = BytesIO()
        workbook.save(output)
        upload = SimpleUploadedFile(
            "catalogo.xlsx",
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        response = self.client.post(
            "/api/v1/admin/catalogo/importar/",
            {"file": upload},
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["libros_creados"], 1)
        self.assertEqual(response.json()["ejemplares_creados"], 1)
        self.assertEqual(response.json()["errores"], [])

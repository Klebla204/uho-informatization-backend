from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
import uuid

from django.db import transaction
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from apps.prestamos.models import Prestamo

from .models import Autor, Biblioteca, Categoria, Editorial, Ejemplar, Libro

MAX_IMPORT_ROWS = 1000
TEMPLATE_COLUMNS = (
    "titulo", "isbn", "autor_principal", "otros_autores", "editorial",
    "año_edicion", "edicion", "categoria", "subcategoria", "resumen",
    "portada_url", "biblioteca", "cantidad_ejemplares", "ubicacion_fisica", "activo",
)
REQUIRED_COLUMNS = {
    "titulo",
    "autor_principal",
    "editorial",
    "año_edicion",
    "categoria",
    "biblioteca",
    "cantidad_ejemplares",
    "activo",
}


@dataclass
class ImportResult:
    processed: int = 0
    created: int = 0
    updated: int = 0
    copies_created: int = 0
    copies_archived: int = 0
    errors: list[dict] = field(default_factory=list)


def _text(value):
    return "" if value is None else str(value).strip()


def _parse_active(value):
    value = _text(value).upper()
    if value not in {"SI", "NO"}:
        raise ValueError("activo debe ser SI o NO")
    return value == "SI"


def _parse_year(value):
    try:
        year = int(value)
    except (TypeError, ValueError):
        raise ValueError("año_edicion debe ser un número entero")
    if year < 1800 or year > datetime.now().year:
        raise ValueError("año_edicion está fuera del rango permitido")
    return year


def _parse_positive_integer(value, field_name):
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} debe ser un número entero")
    if number < 1:
        raise ValueError(f"{field_name} debe ser mayor o igual que 1")
    return number


def _find_or_create_author(value):
    parts = _text(value).split(",", 1)
    if len(parts) != 2 or not all(parts):
        raise ValueError("autor_principal debe tener formato Apellidos, Nombre")
    apellidos, nombre = (part.strip() for part in parts)
    return Autor.objects.get_or_create(nombre=nombre, apellidos=apellidos)[0]


def _authors_from_row(data):
    names = [_text(data.get("autor_principal"))]
    names.extend(value.strip() for value in _text(data.get("otros_autores")).split(";") if value.strip())
    authors = []
    seen = set()
    for name in names:
        author = _find_or_create_author(name)
        if author.id not in seen:
            authors.append(author)
            seen.add(author.id)
    return authors


def _find_or_create_category(value, parent_name=""):
    category, _ = Categoria.objects.get_or_create(nombre=_text(value), defaults={"activa": True})
    if parent_name:
        parent, _ = Categoria.objects.get_or_create(nombre=_text(parent_name), defaults={"activa": True})
        if category.categoria_padre_id != parent.id:
            category.categoria_padre = parent
            category.save(update_fields=["categoria_padre"])
    return category


def _validate_headers(headers):
    missing = REQUIRED_COLUMNS.difference(set(headers))
    if missing:
        raise ValueError(f"faltan columnas obligatorias: {', '.join(sorted(missing))}")


def build_collection_template():
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Libros"
    worksheet.append(TEMPLATE_COLUMNS)
    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = f"A1:{worksheet.cell(row=1, column=len(TEMPLATE_COLUMNS)).column_letter}1"
    for cell in worksheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="245A70")
    for column, width in enumerate((32, 18, 26, 42, 24, 16, 16, 22, 22, 42, 36, 24, 22, 28, 12), start=1):
        worksheet.column_dimensions[worksheet.cell(row=1, column=column).column_letter].width = width

    instructions = workbook.create_sheet("Instrucciones")
    instructions.append(("Columna", "Instrucción"))
    instructions.append(("autor_principal / otros_autores", "Formato Apellidos, Nombre. Separe autores adicionales con punto y coma."))
    instructions.append(("año_edicion", "Año entero entre 1800 y el año actual."))
    instructions.append(("biblioteca", "Nombre exacto de una biblioteca activa."))
    instructions.append(("cantidad_ejemplares", "Cantidad entera positiva deseada para esta biblioteca."))
    instructions.append(("activo", "Use SI o NO."))
    instructions.append(("isbn", "Identificador para actualizar un título existente; si se deja vacío, se crea un título nuevo."))
    instructions.freeze_panes = "A2"
    instructions.column_dimensions["A"].width = 32
    instructions.column_dimensions["B"].width = 100
    for cell in instructions[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="245A70")

    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def _sync_copies(book, library, target_count, location):
    active_copies = Ejemplar.objects.select_for_update().filter(
        libro=book,
        biblioteca=library,
    ).exclude(estado="BAJA")
    current_count = active_copies.count()
    if current_count > target_count:
        excess = current_count - target_count
        protected = Prestamo.objects.filter(
            ejemplar__in=active_copies,
            estado__in={"PENDIENTE", "APROBADO", "LISTO", "ACTIVO"},
        ).values("ejemplar_id")
        removable_ids = list(
            active_copies.filter(estado="DISPONIBLE")
            .exclude(id__in=protected)
            .order_by("id")
            .values_list("id", flat=True)[:excess]
        )
        if len(removable_ids) != excess:
            raise ValueError("no se puede reducir la cantidad: hay ejemplares prestados o reservados")
        Ejemplar.objects.filter(id__in=removable_ids).update(estado="BAJA")
        archived = excess
    else:
        archived = 0

    missing = max(0, target_count - current_count)
    for _ in range(missing):
        Ejemplar.objects.create(
            libro=book,
            biblioteca=library,
            codigo_ejemplar=f"{book.id}-{library.id}-{uuid.uuid4().hex[:12]}",
            ubicacion_fisica=location,
        )
    active_copies.update(ubicacion_fisica=location)
    return missing, archived


def import_collection(file_object, user=None):
    workbook = load_workbook(file_object, read_only=True, data_only=True)
    worksheet = workbook.active
    rows = worksheet.iter_rows(values_only=True)
    headers = [_text(value) for value in next(rows, ())]
    _validate_headers(headers)

    result = ImportResult()
    for row_number, values in enumerate(rows, start=2):
        if result.processed >= MAX_IMPORT_ROWS:
            result.errors.append({"fila": row_number, "motivo": "el límite es de 1000 filas"})
            continue
        if not any(value is not None for value in values):
            continue

        result.processed += 1
        data = dict(zip(headers, values))
        try:
            with transaction.atomic():
                title = _text(data.get("titulo"))
                if not title or len(title) > 500:
                    raise ValueError("titulo es obligatorio y no puede superar 500 caracteres")
                isbn = _text(data.get("isbn")) or None
                editorial, _ = Editorial.objects.get_or_create(nombre=_text(data["editorial"]), defaults={"activa": True})
                category = _find_or_create_category(data["categoria"], data.get("subcategoria"))
                authors = _authors_from_row(data)
                copies = _parse_positive_integer(data["cantidad_ejemplares"], "cantidad_ejemplares")
                library = Biblioteca.objects.get(nombre=_text(data["biblioteca"]), activa=True)
                active = _parse_active(data["activo"])
                defaults = {
                    "titulo": title,
                    "anio_edicion": _parse_year(data["año_edicion"]),
                    "editorial": editorial,
                    "edicion": _text(data.get("edicion")),
                    "resumen": _text(data.get("resumen")),
                    "portada_url": _text(data.get("portada_url")),
                    "activo": active,
                }
                if isbn:
                    book, created = Libro.objects.update_or_create(isbn=isbn, defaults=defaults)
                else:
                    book = Libro.objects.create(**defaults, isbn=None)
                    created = True
                book.autores.set(authors)
                book.categorias.set([category])
                copies_created, copies_archived = _sync_copies(
                    book,
                    library,
                    copies,
                    _text(data.get("ubicacion_fisica")),
                )
            if created:
                result.created += 1
            else:
                result.updated += 1
            result.copies_created += copies_created
            result.copies_archived += copies_archived
        except Exception as error:
            result.errors.append({"fila": row_number, "motivo": str(error)})

    return result

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


TABLES = [
    ("Prestamos por periodo", "prestamos_por_periodo", [("periodo", "Periodo"), ("total", "Prestamos")]),
    ("Prestamos por biblioteca", "prestamos_por_biblioteca", [("biblioteca__nombre", "Biblioteca"), ("total", "Prestamos")]),
    ("Libros mas prestados", "libros_mas_prestados", [("ejemplar__libro__titulo", "Libro"), ("total", "Prestamos")]),
    (
        "Usuarios con mas prestamos",
        "usuarios_mas_prestamos",
        [
            ("usuario__nombre", "Nombre"),
            ("usuario__apellidos", "Apellidos"),
            ("usuario__perfil_estudiante__facultad__nombre", "Facultad"),
            ("usuario__perfil_estudiante__carrera__nombre", "Carrera"),
            ("total", "Prestamos"),
        ],
    ),
    (
        "Prestamos vencidos",
        "prestamos_vencidos",
        [
            ("usuario__nombre", "Nombre"),
            ("usuario__apellidos", "Apellidos"),
            ("ejemplar__libro__titulo", "Libro"),
            ("biblioteca__nombre", "Biblioteca"),
            ("fecha_devolucion_pactada", "Fecha pactada"),
            ("estado", "Estado"),
        ],
    ),
    ("Coleccion por categoria", "coleccion_por_categoria", [("nombre", "Categoria"), ("total", "Ejemplares")]),
]


def _rows(data, key, columns):
    return [[label for _, label in columns]] + [
        [str(row.get(field) or "") for field, _ in columns]
        for row in data[key]
    ]


def build_xlsx(data):
    workbook = Workbook()
    summary = workbook.active
    summary.title = "Resumen"
    summary.append(["Indicador", "Total"])
    summary_rows = [
        ("Desde", data["filtros"]["desde"]),
        ("Hasta", data["filtros"]["hasta"]),
        ("Prestamos totales", data["resumen"]["total_prestamos"]),
        ("Activos", data["resumen"]["activos"]),
        ("Vencidos", data["resumen"]["vencidos"]),
        ("Devoluciones", data["resumen"]["devoluciones"]),
    ]
    for row in summary_rows:
        summary.append(row)
    for title, key, columns in TABLES:
        sheet = workbook.create_sheet(title[:31])
        for row in _rows(data, key, columns):
            sheet.append(row)
    for sheet in workbook.worksheets:
        sheet.freeze_panes = "A2"
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="173A63")
        for column in sheet.columns:
            width = min(max(max(len(str(cell.value or "")) for cell in column) + 2, 12), 42)
            sheet.column_dimensions[column[0].column_letter].width = width
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def build_pdf(data):
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=landscape(letter),
        rightMargin=0.45 * inch,
        leftMargin=0.45 * inch,
        topMargin=0.45 * inch,
        bottomMargin=0.45 * inch,
    )
    styles = getSampleStyleSheet()
    story = [Paragraph("Reportes de prestamos bibliotecarios", styles["Title"])]
    story.append(Paragraph(
        f"Periodo: {data['filtros']['desde']} a {data['filtros']['hasta']} | "
        f"Total: {data['resumen']['total_prestamos']} | "
        f"Activos: {data['resumen']['activos']} | "
        f"Vencidos: {data['resumen']['vencidos']} | "
        f"Devoluciones: {data['resumen']['devoluciones']}",
        styles["Normal"],
    ))
    story.append(Spacer(1, 0.18 * inch))
    for title, key, columns in TABLES:
        story.append(Paragraph(title, styles["Heading2"]))
        table = Table(_rows(data, key, columns), repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#173A63")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C9D2DE")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F9")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.extend([table, Spacer(1, 0.18 * inch)])
    document.build(story)
    return output.getvalue()

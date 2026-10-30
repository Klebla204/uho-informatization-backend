import io

from reportlab.graphics import renderPDF, renderSVG
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.colors import HexColor, white
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

from apps.prestamos.models import Carnet

USER_TYPE_LABELS = {
    "ESTUDIANTE": "Estudiante",
    "TRABAJADOR": "Trabajador",
    "BIBLIOTECARIO": "Bibliotecario",
    "ADMINISTRADOR": "Administrador",
    "SUPER_ADMIN": "Super-Admin",
}


def academic_profile(user):
    student = getattr(user, "perfil_estudiante", None)
    if student:
        return {
            "carrera": student.carrera.nombre,
            "facultad": student.facultad.nombre,
            "anio": student.anio,
            "tipo_curso": student.tipo_curso,
        }
    worker = getattr(user, "perfil_trabajador", None)
    if worker:
        return {"cargo": worker.cargo.nombre, "departamento": worker.departamento, "tipo_contrato": worker.tipo_contrato}
    return None


def profile_complete(user):
    basics = all([user.nombre, user.apellidos, user.ci, user.telefono])
    if user.tipo_usuario == "ESTUDIANTE":
        return basics and getattr(user, "perfil_estudiante", None) is not None
    return bool(basics)


def ensure_carnet(user):
    carnet, _ = Carnet.objects.get_or_create(usuario=user, defaults={"codigo_qr": str(user.id)})
    return carnet


def _qr_drawing(code, size):
    widget = QrCodeWidget(code)
    x1, y1, x2, y2 = widget.getBounds()
    drawing = Drawing(size, size, transform=[size / (x2 - x1), 0, 0, size / (y2 - y1), 0, 0])
    drawing.add(widget)
    return drawing


def qr_svg(code):
    return renderSVG.drawToString(_qr_drawing(code, 200))


def build_carnet_pdf(user, code):
    buffer = io.BytesIO()
    width, height = 85.6 * mm, 54 * mm
    pdf = canvas.Canvas(buffer, pagesize=(width, height))
    pdf.setTitle("Carnet de préstamos BiblioUHO")

    pdf.setFillColor(HexColor("#102a43"))
    pdf.rect(0, height - 11 * mm, width, 11 * mm, stroke=0, fill=1)
    pdf.setFillColor(white)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(5 * mm, height - 7.2 * mm, "BiblioUHO")
    pdf.setFont("Helvetica", 7)
    pdf.drawRightString(width - 5 * mm, height - 7 * mm, "Carnet de préstamos · Universidad de Holguín")

    qr_size = 28 * mm
    renderPDF.draw(_qr_drawing(code, qr_size), pdf, width - qr_size - 4 * mm, 8 * mm)

    text_width = width - qr_size - 13 * mm
    pdf.setFillColor(HexColor("#1b2735"))
    y = height - 17 * mm
    pdf.setFont("Helvetica-Bold", 9)
    for line in simpleSplit(f"{user.nombre} {user.apellidos}".strip(), "Helvetica-Bold", 9, text_width):
        pdf.drawString(5 * mm, y, line)
        y -= 4 * mm

    profile = academic_profile(user) or {}
    details = [f"CI: {user.ci}", USER_TYPE_LABELS.get(user.tipo_usuario, user.tipo_usuario)]
    if "carrera" in profile:
        details += [profile["carrera"], profile["facultad"], f"{profile['anio']}º año · {profile['tipo_curso']}"]
    pdf.setFont("Helvetica", 7)
    for detail in details:
        for line in simpleSplit(detail, "Helvetica", 7, text_width):
            pdf.drawString(5 * mm, y, line)
            y -= 3.2 * mm

    pdf.setFont("Helvetica", 5)
    pdf.setFillColor(HexColor("#667582"))
    pdf.drawString(5 * mm, 3 * mm, f"ID: {code}")
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()

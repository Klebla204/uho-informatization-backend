from datetime import date

from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone

from apps.catalogo.models import Biblioteca, Categoria
from apps.prestamos.models import Prestamo


def build_report_data(start_date=None, end_date=None, library_id=None):
    today = timezone.localdate()
    start_date = start_date or today.replace(day=1)
    end_date = end_date or today

    loans = Prestamo.objects.select_related(
        "usuario", "ejemplar__libro", "biblioteca"
    ).filter(fecha_solicitud__date__gte=start_date, fecha_solicitud__date__lte=end_date)
    copies = Biblioteca.objects.all()
    if library_id:
        loans = loans.filter(biblioteca_id=library_id)
        copies = copies.filter(id=library_id)

    overdue = Prestamo.objects.select_related(
        "usuario", "ejemplar__libro", "biblioteca"
    ).filter(
        Q(estado="VENCIDO")
        | Q(estado="ACTIVO", fecha_devolucion_pactada__date__lt=today)
    )
    if library_id:
        overdue = overdue.filter(biblioteca_id=library_id)

    total = loans.count()
    summary = {
        "total_prestamos": total,
        "activos": loans.filter(estado="ACTIVO").count(),
        "vencidos": overdue.count(),
        "devoluciones": loans.filter(estado="DEVUELTO").count(),
    }

    by_period = list(
        loans.annotate(periodo=TruncMonth("fecha_solicitud"))
        .values("periodo")
        .annotate(total=Count("id"))
        .order_by("periodo")
    )
    by_library = list(
        loans.values("biblioteca_id", "biblioteca__nombre")
        .annotate(total=Count("id"))
        .order_by("-total", "biblioteca__nombre")
    )
    top_books = list(
        loans.values("ejemplar__libro_id", "ejemplar__libro__titulo")
        .annotate(total=Count("id"))
        .order_by("-total", "ejemplar__libro__titulo")[:10]
    )
    top_users = list(
        loans.values(
            "usuario_id",
            "usuario__nombre",
            "usuario__apellidos",
            "usuario__perfil_estudiante__facultad__nombre",
            "usuario__perfil_estudiante__carrera__nombre",
        )
        .annotate(total=Count("id"))
        .order_by("-total", "usuario__apellidos", "usuario__nombre")[:10]
    )
    overdue_rows = list(
        overdue.values(
            "id",
            "usuario__nombre",
            "usuario__apellidos",
            "ejemplar__libro__titulo",
            "biblioteca__nombre",
            "fecha_devolucion_pactada",
            "estado",
        ).order_by("fecha_devolucion_pactada")
    )
    categories = list(
        Categoria.objects.filter(libros__ejemplares__biblioteca__in=copies)
        .values("id", "nombre")
        .annotate(total=Count("libros__ejemplares", distinct=True))
        .order_by("nombre")
    )

    return {
        "filtros": {
            "desde": start_date.isoformat(),
            "hasta": end_date.isoformat(),
            "biblioteca": str(library_id) if library_id else "",
        },
        "bibliotecas": list(Biblioteca.objects.filter(activa=True).values("id", "nombre").order_by("nombre")),
        "resumen": summary,
        "prestamos_por_periodo": [
            {**row, "periodo": row["periodo"].date().isoformat()} for row in by_period
        ],
        "prestamos_por_biblioteca": by_library,
        "libros_mas_prestados": top_books,
        "usuarios_mas_prestamos": top_users,
        "prestamos_vencidos": overdue_rows,
        "coleccion_por_categoria": categories,
    }
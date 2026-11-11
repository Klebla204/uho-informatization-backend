import uuid
from datetime import date

from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalogo.models import Biblioteca
from apps.rbac.models import RolePermission

from .report_services import build_report_data


class CanViewReports(BasePermission):
	message = "Se requiere el permiso reportes.view."

	def has_permission(self, request, view):
		user = request.user
		if not user or not user.is_authenticated:
			return False
		if user.is_superuser:
			return True
		now = timezone.now()
		return RolePermission.objects.filter(
			role__user_roles__user=user,
			permission__name="reportes.view",
			allow=True,
		).filter(
			Q(role__user_roles__expires_at__isnull=True)
			| Q(role__user_roles__expires_at__gt=now)
		).exists()


class ReportsBaseView(APIView):
	permission_classes = [IsAuthenticated, CanViewReports]

	def get_report_data(self, request):
		today = timezone.localdate()
		start_raw = request.query_params.get("desde")
		end_raw = request.query_params.get("hasta")
		start_date = date.fromisoformat(start_raw) if start_raw else today.replace(day=1)
		end_date = date.fromisoformat(end_raw) if end_raw else today
		if start_date > end_date:
			raise ValueError("La fecha inicial debe ser anterior o igual a la fecha final.")

		library_id = request.query_params.get("biblioteca") or None
		if library_id:
			try:
				library_id = uuid.UUID(library_id)
			except ValueError as exc:
				raise ValueError("La biblioteca indicada no es válida.") from exc
			if not Biblioteca.objects.filter(pk=library_id).exists():
				raise ValueError("La biblioteca indicada no existe.")
		return build_report_data(start_date, end_date, library_id)

	def get(self, request):
		try:
			return Response(self.get_report_data(request))
		except ValueError as exc:
			return Response({"detail": str(exc)}, status=400)


class ReportsExportView(ReportsBaseView):
	def get(self, request):
		try:
			data = self.get_report_data(request)
		except ValueError as exc:
			return Response({"detail": str(exc)}, status=400)

		export_format = request.query_params.get("formato", "xlsx").lower()
		if export_format == "xlsx":
			from .report_exports import build_xlsx

			response = HttpResponse(
				build_xlsx(data),
				content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
			)
			response["Content-Disposition"] = 'attachment; filename="reportes-biblioteca.xlsx"'
			return response
		if export_format == "pdf":
			from .report_exports import build_pdf

			response = HttpResponse(build_pdf(data), content_type="application/pdf")
			response["Content-Disposition"] = 'attachment; filename="reportes-biblioteca.pdf"'
			return response
		return Response({"detail": "Formato no válido. Use xlsx o pdf."}, status=400)

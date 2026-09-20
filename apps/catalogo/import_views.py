from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from drf_spectacular.utils import extend_schema

from apps.rbac.drf_permissions import HasCatalogPermission

from .import_services import import_collection
from .import_serializers import CollectionImportResultSerializer, CollectionImportSerializer


class CollectionImportView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (HasCatalogPermission,)
    parser_classes = (MultiPartParser,)
    required_permission = "catalogo.manage"

    @extend_schema(
        request=CollectionImportSerializer,
        responses=CollectionImportResultSerializer,
    )
    def post(self, request):
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response({"detail": "Debe enviar el fichero en el campo file."}, status=status.HTTP_400_BAD_REQUEST)
        if not uploaded_file.name.lower().endswith(".xlsx"):
            return Response({"detail": "Solo se aceptan ficheros .xlsx."}, status=status.HTTP_400_BAD_REQUEST)

        result = import_collection(uploaded_file, user=request.user)
        return Response(
            {
                "filas_procesadas": result.processed,
                "libros_creados": result.created,
                "libros_actualizados": result.updated,
                "ejemplares_creados": result.copies_created,
                "errores": result.errors,
            },
            status=status.HTTP_200_OK,
        )

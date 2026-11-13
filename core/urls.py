import os

from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from drf_spectacular.utils import extend_schema, extend_schema_view


token_obtain_view = extend_schema_view(
    post=extend_schema(
        summary="Obtener tokens JWT",
        description="Intercambia las credenciales locales por access y refresh tokens. El access token se envía como Bearer en endpoints protegidos.",
        tags=["Autenticación"],
    )
)(TokenObtainPairView).as_view()
token_refresh_view = extend_schema_view(
    post=extend_schema(
        summary="Renovar token JWT",
        description="Emite un nuevo access token a partir de un refresh token válido.",
        tags=["Autenticación"],
    )
)(TokenRefreshView).as_view()

urlpatterns = [
    path("", RedirectView.as_view(url=os.getenv("FRONTEND_HOME_URL", "http://localhost:5173/pages/catalogo.html"))),
    path("admin/", admin.site.urls),
    path("api/token/", token_obtain_view, name="token_obtain_pair"),
    path("api/token/refresh/", token_refresh_view, name="token_refresh"),
    path("auth/", include("apps.uho_auth.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema")),
    path("api/v1/", include("apps.catalogo.urls")),
    path("api/v1/admin/catalogo/", include("apps.catalogo.crud_urls")),
    path("api/v1/admin/rbac/", include("apps.rbac.urls")),
    path("api/v1/reportes/", include("apps.analytics.urls")),
    path("api/v1/admin/auditoria/", include("apps.auditoria.urls")),
    path("api/v1/prestamos/", include("apps.prestamos.urls")),
    path("api/v1/usuarios/", include("apps.users.urls")),
    path("api/example/", include("apps.example.urls")),
]
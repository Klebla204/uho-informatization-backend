import os

from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("", RedirectView.as_view(url=os.getenv("FRONTEND_LOGIN_URL", "http://localhost:5173/login.html"))),
    path("admin/", admin.site.urls),
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/", include("apps.uho_auth.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema")),
    path("api/v1/", include("apps.catalogo.urls")),
    path("api/v1/admin/catalogo/", include("apps.catalogo.crud_urls")),
    path("api/v1/prestamos/", include("apps.prestamos.urls")),
    path("api/v1/usuarios/", include("apps.users.urls")),
    path("api/example/", include("apps.example.urls")),
]
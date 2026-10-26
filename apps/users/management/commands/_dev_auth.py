import os

from django.conf import settings
from django.core.management.base import CommandError


def require_local_demo_mode():
    enabled = os.getenv("ENABLE_LOCAL_DEMO_AUTH", "").strip().lower() in {"1", "true", "yes", "on"}
    database_engine = settings.DATABASES["default"]["ENGINE"]
    if not settings.DEBUG or not enabled or database_engine != "django.db.backends.sqlite3":
        raise CommandError(
            "Comando bloqueado: requiere DEBUG=True, ENABLE_LOCAL_DEMO_AUTH=true y SQLite local. "
            "Este modo no es para producción ni sustituye la autenticación institucional."
        )

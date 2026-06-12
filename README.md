# Backend — Sistema de Informatización (UHO)

Este documento describe la arquitectura, alcance y pasos prácticos para el backend del proyecto de informatización de la Universidad de Holguín (UHO).

## Visión general
El backend es una API REST construida con Django y Django REST Framework. Está organizado en apps modulares (students, academics, hr, maintenance, research, analytics, ai, etc.) y expone endpoints consumidos por el frontend.

Objetivos principales:
- Proveer API seguras y versionadas.
- Soportar RBAC (control de acceso basado en roles) y auditoría de acciones.
- Ser desplegable en Docker y escalable con PostgreSQL y MinIO.

## Alcance
Incluye:
- Gestión de usuarios y roles (RBAC).
- Módulos para estudiantes, académicos, RRHH, mantenimiento, investigación y analítica.
- Integración con sistemas de almacenamiento de objetos (MinIO) y servicios AI (APIs internas/external).

No incluye (por ahora): integración con sistemas externos legacy específicos (se evaluará caso a caso).

## Diagrama de arquitectura (resumen)

- Clientes (Web, Mobile)
	-> Frontend (React/Vite) 
	-> Comunicación por HTTPS a la API Django REST
- Backend (Django)
	- Apps modulares (cada dominio como una app)
	- Autenticación: JWT (Simple JWT)
	- Autorización: RBAC (apps.rbac)
	- Auditoría: middleware que registra operaciones importantes
	- Storage: MinIO (S3 compatible) para archivos y activos
	- DB: PostgreSQL (producción), SQLite (temporal desarrollo)

## RBAC — Resumen
- Implementación en `apps.rbac` con modelos: Role, Permission, RolePermission, UserRole y RoleHierarchy.
- Command para sembrar roles/permisos por defecto: `python manage.py seed_roles`.
- Comando helper para aplicar migraciones + semilla: `python manage.py apply_rbac` (usa `makemigrations` y `migrate` para la app y luego ejecuta `seed_roles`).

## Seguridad
- Autenticación: JWT (djangorestframework-simplejwt).
- Control de acceso: permisos asignados a roles; roles asignados a usuarios (posibilidad de alcance por recurso).
- Recomendaciones: proteger `main` y `develop` en GitHub, requerir PR y checks antes de merge.

## Despliegue
- En producción se recomienda usar Docker + docker-compose o Kubernetes, con servicios:
	- Postgres (persistente)
	- MinIO (persistente)
	- Servicio web (Gunicorn/uvicorn detrás de Nginx)
	- Redis (opcional, cache / Celery broker)

## Desarrollo local (rápido)
Requisitos: Python 3.11+, Docker (opcional) y Node.js para frontend.

1) Crear y activar virtualenv (PowerShell):
```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1
```

2) Instalar dependencias:
```powershell
pip install -r backend\requirements.txt
```

3) Para desarrollo rápido usar SQLite temporal (no afecta producción):
```powershell
$root = (Get-Location).Path -replace '\\','/'
$env:DATABASE_URL = "sqlite:///$root/backend/db.sqlite3"
python backend\manage.py makemigrations
python backend\manage.py migrate
```

4) Crear migraciones y semilla RBAC (helper):
```powershell
python backend\manage.py apply_rbac
# o si prefieres solo sembrar después de migraciones:
python backend\manage.py seed_roles
```

5) Ejecutar servidor de desarrollo:
```powershell
python backend\manage.py runserver
```

Si prefieres usar Docker (recomendado para replicar producción):
```powershell
# ejemplo rápido (necesita un docker-compose.yml apropiado)
docker compose up -d
```

## Migrar de SQLite a PostgreSQL (script)

Se incluye un helper PowerShell para automatizar la creación de la base de datos/usuario en Postgres,
volcar los datos desde SQLite y ejecutar migraciones: `scripts/migrate_sqlite_to_postgres.ps1`.

Uso recomendado (desde `backend` con el virtualenv activado):

PowerShell:

```powershell
# Ejecuta el script (te puede pedir la contraseña del superusuario postgres)
.\scripts\migrate_sqlite_to_postgres.ps1 -PgSuperUser postgres

# Si necesitas pasar la contraseña del superuser (temporalmente) para llamadas psql:
.\scripts\migrate_sqlite_to_postgres.ps1 -PgSuperUser postgres -PgSuperPassword 'TuPassword'
```

El script crea el usuario/BD (si no existen), realiza `dumpdata` desde la SQLite actual,
aplica `migrate` en Postgres y luego `loaddata`.

Notas:
- Haz un backup del archivo `db.sqlite3` antes de ejecutar el script.
- Si `loaddata` falla por dependencias complejas, prueba exportar y cargar app por app.
- Para migraciones grandes o si deseas conservar tipos/constraints exactamente como en producción,
  considera usar `pgloader` desde WSL o una herramienta ETL especializada.

## CI / QA
- El repo contiene una GitHub Action (`.github/workflows/ci.yml`) que corre tests del backend usando una imagen de Postgres en Actions. Revisa y adapta el workflow si cambias versiones de Python/Postgres.

## Contribuir
- Sigue el flujo Git: `feature/*` -> `develop` -> `main`.
- Usa PRs y asigna reviewers. Añade tests y actualiza documentación.

## Contacto / Mantenimiento
- Mantener actualizadas las dependencias en `backend/requirements.txt`.
- Documentar cambios de esquema (migraciones) y política de retención de datos.

## Roadmap

A continuación hay un mapa de ruta (roadmap) con la lista de verificación de los módulos lógicos pendientes que estructurarán el trabajo. Marca cada ítem cuando esté completamente implementado (modelos, migraciones, endpoints, tests y documentación).

- [ ] users — Gestión avanzada de usuarios (perfiles extendidos, importación masiva, recuperación de contraseñas)
- [x] rbac — Roles y permisos (migraciones aplicadas, semilla disponible)
- [ ] students — CRUD completo, importación de matrículas, validaciones académicas
- [ ] academics — Gestión de cursos, asignaturas, horarios y programas
- [ ] hr — Gestión de personal, contratos, permisos y nóminas
- [ ] maintenance — Gestión de incidencias y solicitudes de mantenimiento
- [ ] research — Registro de proyectos, financiamiento y publicaciones
- [ ] analytics — Dashboards y endpoints para agregaciones y KPIs
- [ ] ai — Integraciones experimentales con servicios AI (p.ej. resumen de documentos)
- [ ] storage — Integración completa con MinIO (políticas, backups y lifecycle)
- [ ] ci-cd — Pipelines completas para tests, linting y despliegue en staging/prod
- [ ] dockerization — Composables y documentación para despliegue reproducible
- [ ] backups & migrations — Estrategia de backups, migraciones seguras y restauración

Notas:
- Cada módulo debe incluir: modelos, migraciones, API endpoints, permisos RBAC, tests unitarios/integración y documentación de uso.
- Prioridad inicial: `users`, `rbac` (completado), `students` y `academics`.
- Propuesta de milestones: Sprint 1 (users + rbac + students básico), Sprint 2 (academics + hr), Sprint 3 (maintenance + research + analytics), Sprint 4 (ai + storage + hardening).

---
Este README debe usarse como documento de arquitectura y alcance inicial del backend; se sugiere mantenerlo sincronizado con la documentación formal del proyecto.

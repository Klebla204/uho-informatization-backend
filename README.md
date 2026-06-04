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

## CI / QA
- El repo contiene una GitHub Action (`.github/workflows/ci.yml`) que corre tests del backend usando una imagen de Postgres en Actions. Revisa y adapta el workflow si cambias versiones de Python/Postgres.

## Contribuir
- Sigue el flujo Git: `feature/*` -> `develop` -> `main`.
- Usa PRs y asigna reviewers. Añade tests y actualiza documentación.

## Contacto / Mantenimiento
- Mantener actualizadas las dependencias en `backend/requirements.txt`.
- Documentar cambios de esquema (migraciones) y política de retención de datos.

---
Este README debe usarse como documento de arquitectura y alcance inicial del backend; se sugiere mantenerlo sincronizado con la documentación formal del proyecto.

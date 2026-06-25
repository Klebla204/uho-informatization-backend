# Backend — Sistema de Gestion de Préstamos Bibliotecarios (BiblioUHO)

Este documento describe la arquitectura, alcance y pasos prácticos para el backend del proyecto de informatización de la gestion de prestamos bibliotecarios en la Universidad de Holguín (UHO).

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
	- DB: PostgreSQL (producción)

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

## ⚙️ Roadmap Backend – BiblioUHO

## 🚀 Fase 1: Configuración Inicial
- [ ] **[Stack tecnológico](ca://s?q=Definir_Stack_Tecnológico)** – configuración de entorno con Node.js/NestJS o Django, PostgreSQL y Docker Compose  
- [ ] **[Estructura de capas](ca://s?q=Diseñar_Estructura_de_Capas)** – separación en controladores, servicios, repositorios y modelos  
- [ ] **[Autenticación institucional](ca://s?q=Implementar_Autenticación_Institucional)** – integración con auth.uho.edu.cu vía OAuth2/LDAP  
- [ ] **[Gestión de roles y permisos](ca://s?q=Construir_Gestión_de_Roles_y_Permisos)** – control granular de accesos por módulo  



## 📚 Fase 2: Gestión de Datos
- [ ] **[Modelo de datos](ca://s?q=Construir_Modelo_de_Datos)** – entidades usuarios, préstamos, catálogo, perfiles de estudiante/trabajador  
- [ ] **[CRUD de catálogo](ca://s?q=Implementar_CRUD_de_Catálogo)** – títulos, ejemplares, autores, editoriales, categorías  
- [ ] **[Nomencladores CRUD](ca://s?q=Desarrollar_Nomencladores_CRUD)** – facultades, carreras, tipos de curso, cargos, bibliotecas  
- [ ] **[Importación Excel](ca://s?q=Implementar_Importación_Excel_Backend)** – validación de datos, reporte de errores y actualización masiva  



## 🔑 Fase 3: Gestión de Préstamos
- [ ] **[Solicitud en línea](ca://s?q=Construir_Solicitud_en_Línea_Backend)** – verificación de disponibilidad y estado “Pendiente”  
- [ ] **[Préstamo presencial](ca://s?q=Implementar_Préstamo_Presencial_Backend)** – registro directo por bibliotecario con carnet QR  
- [ ] **[Renovación de préstamo](ca://s?q=Desarrollar_Renovación_de_Préstamo_Backend)** – validación de reservas pendientes antes de aprobar  
- [ ] **[Lista de espera](ca://s?q=Construir_Lista_de_Espera_Backend)** – notificación automática al primer usuario cuando se libera un ejemplar  
- [ ] **[Multas y sanciones](ca://s?q=Implementar_Multas_y_Sanciones)** – bloqueo temporal de solicitudes por préstamos vencidos  


## 📡 Fase 4: Interoperabilidad y API
- [ ] **[API REST](ca://s?q=Construir_API_REST_Backend)** – endpoints para catálogo, disponibilidad y estado de préstamos (JWT)  
- [ ] **[Documentación OpenAPI](ca://s?q=Generar_Documentación_OpenAPI)** – especificación 3.0 para consumo externo  
- [ ] **[Integración con SIGENU](ca://s?q=Integrar_SIGENU_Backend)** – sincronización de datos académicos de estudiantes  
- [ ] **[Integración con ASSET](ca://s?q=Integrar_ASSET_Backend)** – sincronización de datos laborales de trabajadores  
- [ ] **[Panel multibiblioteca](ca://s?q=Construir_Panel_Multibiblioteca_Backend)** – gestión consolidada de las cuatro bibliotecas  


## 🛡️ Fase 5: Seguridad y Auditoría
- [ ] **[Logs de auditoría](ca://s?q=Implementar_Logs_de_Auditoría)** – registro de acciones con timestamp, usuario, entidad e IP  
- [ ] **[Protección OWASP](ca://s?q=Aplicar_Protecciones_OWASP)** – CSRF, XSS, SQL Injection, validación de entradas  
- [ ] **[Cifrado de datos sensibles](ca://s?q=Implementar_Cifrado_de_Datos)** – almacenamiento seguro de CI y teléfono  
- [ ] **[TLS/HTTPS](ca://s?q=Configurar_TLS_y_HTTPS)** – comunicación cifrada con certificados válidos  



## 📊 Fase 6: Reportes y Optimización
- [ ] **[Reportes y estadísticas](ca://s?q=Generar_Reportes_Backend)** – préstamos por período, biblioteca, usuarios destacados, vencidos  
- [ ] **[Exportación PDF/Excel](ca://s?q=Implementar_Exportación_PDF_Excel)** – generación de reportes descargables  
- [ ] **[Performance](ca://s?q=Optimizar_Performance_Backend)** – consultas rápidas y escalabilidad para nuevas bibliotecas  
- [ ] **[Cobertura de tests](ca://s?q=Implementar_Tests_Backend)** – mínimo 60% de cobertura en pruebas unitarias e integración  
- [ ] **[Mantenibilidad](ca://s?q=Mejorar_Mantenibilidad_Backend)** – estándares de codificación y documentación técnica actualizada

Notas:
- Cada módulo debe incluir: modelos, migraciones, API endpoints, permisos RBAC, tests unitarios/integración y documentación de uso.
- Prioridad inicial: `users`, `rbac` (completado), `students` y `academics`.
- Propuesta de milestones: Sprint 1 (users + rbac + students básico), Sprint 2 (academics + hr), Sprint 3 (maintenance + research + analytics), Sprint 4 (ai + storage + hardening).


Este README debe usarse como documento de arquitectura y alcance inicial del backend; se sugiere mantenerlo sincronizado con la documentación formal del proyecto.

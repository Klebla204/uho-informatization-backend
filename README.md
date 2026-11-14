# Backend BiblioUHO

API REST del sistema BiblioUHO, construida con Django, Django REST Framework y JWT. Esta guía permite instalarla desde un clon nuevo del repositorio.

## Requisitos

- Python 3.11 o superior (el proyecto también se valida con Python 3.13).
- Git.
- PostgreSQL solo si se elige ese motor; por defecto se usa SQLite.

## Instalación local

Los comandos se muestran desde la raíz del repositorio.

### Windows PowerShell

```powershell
git clone <URL_DEL_REPOSITORIO>
cd uho-dev-system
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
```

Si PowerShell bloquea la activación del entorno, ejecuta `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` en esa terminal y activa de nuevo.

### Linux / macOS

```bash
git clone <URL_DEL_REPOSITORIO>
cd uho-dev-system
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
```

## Configuración

Edita `backend/.env`. No subas ese archivo al repositorio.

- `DJANGO_SECRET_KEY`: clave secreta única y aleatoria. No uses la de ejemplo en un servidor compartido.
- `DJANGO_DEBUG`: `true` para desarrollo; `false` en producción.
- `DJANGO_ALLOWED_HOSTS`: nombres/IP por los que se accede al backend, separados por comas y sin esquema ni puerto.
- `CORS_ALLOWED_ORIGINS`: orígenes frontend completos, separados por comas, con esquema y puerto cuando aplique.
- `FRONTEND_HOME_URL`: destino de la redirección de `/` en Django; por defecto apunta al catálogo local de Vite.
- `USE_POSTGRES`: por defecto `false`, por lo que se utiliza `backend/db.sqlite3`.
- `DATABASE_URL`: URL PostgreSQL requerida al activar `USE_POSTGRES=true`, por ejemplo `postgresql://usuario:clave@localhost:5432/uho_db`.
- `UHO_API_KEY`, `UHO_AUTH_URL` y `UHO_AUTH_ORIGIN`: opcionales; se usan para la autenticación institucional cuando el proveedor está habilitado.

La aplicación busca `backend/.env`. Las variables definidas en el entorno del sistema también son válidas y tienen precedencia según `python-dotenv`.

## Base de datos y roles

Desde la raíz, con el entorno virtual activado:

```powershell
python backend\manage.py migrate
python backend\manage.py seed_roles
```

En Linux/macOS, sustituye las barras inversas:

```bash
python backend/manage.py migrate
python backend/manage.py seed_roles
```

`migrate` aplica las migraciones incluidas en el repositorio. `seed_roles` crea los permisos y roles RBAC predefinidos y se puede ejecutar de nuevo sin duplicarlos.

Para crear una cuenta administradora local:

```bash
python backend/manage.py createsuperuser
```

Para verificar la instalación:

```bash
python backend/manage.py check
python backend/manage.py test apps.rbac.tests apps.uho_auth.tests apps.catalogo.tests apps.prestamos.tests apps.analytics.tests apps.auditoria.tests --noinput
```

## Levantar la API

```bash
python backend/manage.py runserver 127.0.0.1:8000
```

La API estará en `http://127.0.0.1:8000`. La documentación Swagger/OpenAPI está en `http://127.0.0.1:8000/api/docs/` y el esquema JSON en `/api/schema/`.

## Acceso desde otra computadora en la red

1. Averigua la IP local del equipo que ejecuta Django, por ejemplo `192.168.1.25`.
2. En `backend/.env`, configura `DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.25`.
3. En `frontend/src/.env`, configura `VITE_API_URL=http://192.168.1.25:8000`.
4. Agrega el origen del frontend en `CORS_ALLOWED_ORIGINS`, por ejemplo `http://192.168.1.25:5173`.
5. Si se usa la redirección `/` del backend, configura `FRONTEND_HOME_URL=http://192.168.1.25:5173/pages/catalogo.html`.
6. Reinicia los servidores después de cambiar `.env` y permite los puertos 8000/5173 en el firewall solo dentro de la red de confianza.
7. Inicia Django escuchando en la interfaz de red:

```bash
python backend/manage.py runserver 0.0.0.0:8000
```

No uses `runserver` como servidor de producción. Para producción se requiere un servidor WSGI/ASGI, HTTPS, `DJANGO_DEBUG=false`, una clave propia y un motor de base de datos con respaldos.

## PostgreSQL opcional

Instala y arranca PostgreSQL, crea una base de datos y un usuario, y configura en `backend/.env`:

```dotenv
USE_POSTGRES=true
DATABASE_URL=postgresql://usuario:clave@localhost:5432/uho_db
```

Luego ejecuta `python backend/manage.py migrate`. Mantén las credenciales fuera de Git.

## Tareas habituales

```bash
python backend/manage.py makemigrations
python backend/manage.py migrate
python backend/manage.py seed_roles
python backend/manage.py notificar_vencimientos
```

`notificar_vencimientos` debe programarse diariamente si se desea emitir notificaciones automáticas de vencimiento.

## Roadmap del backend

Estado contrastado con el documento [Sistema Integrado de Gestión de Préstamos Bibliotecarios (BiblioUHO)_Requerimientos.pdf](../Sistema%20Integrado%20de%20Gesti%C3%B3n%20de%20Pr%C3%A9stamos%20Bibliotecarios%28BiblioUHO%29_Requerimientos.pdf) y el código/tests actuales. `[x]` significa completado en el alcance descrito; `[ ] Parcial` indica que existe funcionalidad pero falta cerrar parte del requisito; `[ ] Pendiente` indica trabajo no implementado.

### E1-E2: Base, usuarios y autenticación

- [x] API Django REST, JWT, perfiles, roles y permisos RBAC (RF-13, RF-15).
- [x] Perfil de estudiante, validación de completitud, carnet QR y descarga PDF (RF-04).
- [ ] Parcial: autenticación contra `auth.uho.edu.cu` mediante cliente institucional y API key; falta el flujo OAuth2/OIDC Authorization Code + PKCE descrito en el PDF (RF-03).
- [ ] Pendiente: sincronización de perfiles con SIGENU y ASSET en el primer acceso y de forma programada (RF-03, integración externa).
- [ ] Pendiente: definir el proceso de actualización y verificación de datos personales, incluyendo consentimiento y consulta/exportación de datos.

### E3: Catálogo y nomencladores

- [x] API pública de libros, detalle, filtros y disponibilidad por biblioteca (RF-01, RF-02).
- [x] CRUD administrativo de libros, ejemplares, autores, categorías, editoriales y bibliotecas (RF-10).
- [x] Importación Excel con plantilla, validación por fila y límite de 1000 filas (RF-11).
- [ ] Parcial: CRUD completo de nomencladores académicos y laborales (facultades, carreras, cargos y departamentos) desde administración (RF-12).
- [ ] Pendiente: almacenar y servir portadas y archivos en almacenamiento de objetos configurable (RF-02, arquitectura sugerida).

### E4-E5: Préstamos y notificaciones

- [x] Solicitud en línea, control de ejemplar disponible y estados pendiente/aprobado/listo/activo/devuelto/rechazado (RF-05, RF-06).
- [x] Fecha pactada ingresada por bibliotecario al registrar la entrega; préstamo presencial directo con fecha de devolución (RF-06, RF-07, RF-08).
- [x] Registro de devolución y liberación del ejemplar (RF-06).
- [x] Notificaciones in-app de vencimiento próximo y vencido, más consulta de vencimientos por biblioteca (RF-08).
- [ ] Parcial: el modelo de lista de espera existe, pero falta inscripción/API, orden de cola y notificación automática al liberar un ejemplar (RF-18).
- [ ] Pendiente: solicitud y aprobación de renovación (RF-19).
- [ ] Pendiente: registro de sanciones y bloqueo temporal de solicitudes (RF-20).
- [ ] Parcial: notificaciones por correo y procesamiento asíncrono; actualmente los avisos de vencimiento se generan mediante comando y notificaciones in-app (RF-08, RNF-14).

### E6: Reportes, auditoría y API

- [x] API documentada con OpenAPI/Swagger y autenticación JWT (RF-15).
- [x] Reportes de préstamos, bibliotecas, libros, usuarios, vencimientos y colección, con exportación PDF/XLSX (RF-14).
- [x] Registro de auditoría con usuario, acción, entidad, IP y datos de cambios para operaciones instrumentadas (RF-16).
- [ ] Parcial: ampliar cobertura de auditoría a todas las acciones sensibles y definir retención mínima de 90 días (RF-16, RNF-11).
- [ ] Parcial: el panel multibiblioteca y el aislamiento por sede están implementados en el API/RBAC; falta completar indicadores de estado global de las cuatro bibliotecas (RF-17).

### E7-E9: Calidad, seguridad e instalación

- [x] Pruebas automatizadas de autenticación, RBAC, catálogo, préstamos, auditoría y analítica; CI ejecuta pruebas del backend.
- [ ] Pendiente: medir y alcanzar cobertura mínima de 60%, añadir pruebas de carga (200 usuarios) y revisión OWASP documentada (RNF-01, RNF-03, RNF-08).
- [ ] Parcial: despliegue Docker Compose con PostgreSQL, Redis y MinIO definidos; completar configuración segura de secretos, migraciones/seed automáticos, almacenamiento y procedimiento de producción (RNF-09).
- [ ] Pendiente: configuración operativa de HTTPS/TLS, respaldos, monitorización y objetivo de disponibilidad ≥95% (RNF-02, RNF-03).
- [x] Guía de instalación local, variables de entorno y configuración de red documentadas en este README.

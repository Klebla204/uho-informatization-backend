 # Development System for an Informatization Process for the University of Holguín (UHO)

Este sistema constituye una plataforma modular institucional diseñada para soportar los procesos clave de la Universidad de Holguín, incluyendo:

- Gestión de Estudiantes  
- Procesos Académicos  
- Recursos Humanos  
- Gestión de Mantenimiento  
- Proyectos de Investigación  
- Analítica Universitaria  
- Inteligencia Artificial aplicada a procesos educativos y administrativos  

## Objetivo General
Proveer una arquitectura escalable, segura y adaptable a la infraestructura universitaria cubana, permitiendo la informatización progresiva de los procesos institucionales.

## Arquitectura
El sistema está compuesto por:

- **Backend Django REST Framework**
- **Frontend React + Vite + Tailwind**
- **Base de datos PostgreSQL**
- **MinIO para almacenamiento**
- **Docker para despliegue**
- **GitLab CI/CD para integración continua**

## Modularidad
Cada módulo se implementa como una app independiente en Django y como una sección autónoma en el frontend React.

## Seguridad
El sistema utiliza JWT y RBAC (Role-Based Access Control) para garantizar la separación lógica de permisos institucionales.

## Auditoría y Backups
Incluye middleware de auditoría y scripts automáticos de respaldo PostgreSQL.

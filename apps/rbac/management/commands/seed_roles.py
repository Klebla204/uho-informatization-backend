from django.core.management.base import BaseCommand
from apps.rbac.models import Role, Permission, RolePermission


DEFAULT_ROLES = [
    {'name': 'visitante', 'display_name': 'Visitante', 'is_system': True},
    {'name': 'estudiante', 'display_name': 'Estudiante', 'is_system': True},
    {'name': 'trabajador', 'display_name': 'Trabajador', 'is_system': True},
    {'name': 'bibliotecario', 'display_name': 'Bibliotecario', 'is_system': True},
    {'name': 'administrador_biblioteca', 'display_name': 'Administrador de Biblioteca', 'is_system': True},
    {'name': 'super_admin', 'display_name': 'Super-Admin', 'is_system': True},
]

DEFAULT_PERMISSIONS = [
    {'name': 'catalogo.view', 'description': 'Consultar catálogo'},
    {'name': 'catalogo.manage', 'description': 'Gestionar catálogo y ejemplares'},
    {'name': 'prestamos.request', 'description': 'Solicitar préstamos'},
    {'name': 'prestamos.manage', 'description': 'Gestionar préstamos y devoluciones'},
    {'name': 'reportes.view', 'description': 'Consultar reportes'},
    {'name': 'admin.manage', 'description': 'Gestionar configuración institucional'},
]

ROLE_PERMISSIONS = {
    'visitante': ['catalogo.view'],
    'estudiante': ['catalogo.view', 'prestamos.request'],
    'trabajador': ['catalogo.view', 'prestamos.request'],
    'bibliotecario': ['catalogo.view', 'catalogo.manage', 'prestamos.manage'],
    'administrador_biblioteca': ['catalogo.view', 'catalogo.manage', 'prestamos.manage', 'reportes.view'],
    'super_admin': [
        'catalogo.view', 'catalogo.manage', 'prestamos.request',
        'prestamos.manage', 'reportes.view', 'admin.manage',
    ],
}


class Command(BaseCommand):
    help = 'Seed default roles and permissions for the RBAC system'

    def handle(self, *args, **options):
        self.stdout.write('Seeding permissions...')
        for p in DEFAULT_PERMISSIONS:
            perm, created = Permission.objects.get_or_create(name=p['name'], defaults={'description': p.get('description', '')})
            if created:
                self.stdout.write(f'  Created permission: {perm.name}')

        self.stdout.write('Seeding roles...')
        for r in DEFAULT_ROLES:
            role, created = Role.objects.get_or_create(name=r['name'], defaults={'display_name': r.get('display_name', ''), 'is_system': r.get('is_system', False)})
            if created:
                self.stdout.write(f'  Created role: {role.name}')

        self.stdout.write('Assigning permissions to roles...')
        for role_name, perms in ROLE_PERMISSIONS.items():
            try:
                role = Role.objects.get(name=role_name)
            except Role.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Role {role_name} not found'))
                continue
            for perm_name in perms:
                try:
                    perm = Permission.objects.get(name=perm_name)
                except Permission.DoesNotExist:
                    self.stdout.write(self.style.ERROR(f'Permission {perm_name} not found'))
                    continue
                rp, created = RolePermission.objects.get_or_create(role=role, permission=perm)
                if created:
                    self.stdout.write(f'  Granted {perm_name} to {role_name}')

        self.stdout.write(self.style.SUCCESS('RBAC seed completed.'))

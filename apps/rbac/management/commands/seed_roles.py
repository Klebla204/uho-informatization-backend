from django.core.management.base import BaseCommand
from apps.rbac.models import Role, Permission, RolePermission


DEFAULT_ROLES = [
    {'name': 'admin', 'display_name': 'Administrator', 'is_system': True},
    {'name': 'editor', 'display_name': 'Editor', 'is_system': True},
    {'name': 'viewer', 'display_name': 'Viewer', 'is_system': True},
]

DEFAULT_PERMISSIONS = [
    {'name': 'students.view', 'description': 'View students'},
    {'name': 'students.edit', 'description': 'Edit students'},
    {'name': 'courses.view', 'description': 'View courses'},
    {'name': 'courses.edit', 'description': 'Edit courses'},
]

ROLE_PERMISSIONS = {
    'admin': ['students.view', 'students.edit', 'courses.view', 'courses.edit'],
    'editor': ['students.view', 'students.edit', 'courses.view', 'courses.edit'],
    'viewer': ['students.view', 'courses.view'],
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

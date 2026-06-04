from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.conf import settings


class Command(BaseCommand):
    help = 'Create and apply migrations for rbac app and seed default roles/permissions.'

    def handle(self, *args, **options):
        app_name = 'rbac'
        full_app = 'apps.rbac'

        if full_app not in settings.INSTALLED_APPS:
            self.stdout.write(self.style.ERROR(f"'{full_app}' is not in INSTALLED_APPS. Please add it to your settings before running this command."))
            return

        self.stdout.write('Making migrations for rbac...')
        call_command('makemigrations', app_name)

        self.stdout.write('Applying migrations...')
        call_command('migrate', app_name)

        self.stdout.write('Seeding default roles and permissions...')
        call_command('seed_roles')

        self.stdout.write(self.style.SUCCESS('RBAC migrations applied and data seeded.'))

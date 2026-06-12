from django.db import migrations


class Migration(migrations.Migration):
	# Empty migration to resolve previous placeholders; depends on the new 0001
	initial = False
	dependencies = [
		('rbac', '0001_initial'),
	]
	operations = []

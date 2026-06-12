from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Role',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('display_name', models.CharField(max_length=200, blank=True)),
                ('description', models.TextField(blank=True)),
                ('is_system', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='Permission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, unique=True)),
                ('description', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='RolePermission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('resource_type', models.CharField(max_length=100, null=True, blank=True)),
                ('resource_id', models.CharField(max_length=200, null=True, blank=True)),
                ('allow', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('permission', models.ForeignKey(on_delete=models.deletion.CASCADE, to='rbac.permission')),
                ('role', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='role_permissions', to='rbac.role')),
            ],
            options={
                'unique_together': {('role', 'permission', 'resource_type', 'resource_id')},
            },
        ),
        migrations.CreateModel(
            name='UserRole',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('resource_type', models.CharField(max_length=100, null=True, blank=True)),
                ('resource_id', models.CharField(max_length=200, null=True, blank=True)),
                ('assigned_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField(null=True, blank=True)),
                ('assigned_by', models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name='+', to='users.CustomUser')),
                ('role', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='user_roles', to='rbac.role')),
                ('user', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='user_roles', to='users.CustomUser')),
            ],
            options={
                'unique_together': {('user', 'role', 'resource_type', 'resource_id')},
            },
        ),
        migrations.CreateModel(
            name='RoleHierarchy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('child', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='parents', to='rbac.role')),
                ('parent', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='children', to='rbac.role')),
            ],
            options={
                'unique_together': {('parent', 'child')},
            },
        ),
    ]

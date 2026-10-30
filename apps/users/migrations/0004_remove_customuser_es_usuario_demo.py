from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_customuser_es_usuario_demo'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='customuser',
            name='es_usuario_demo',
        ),
    ]

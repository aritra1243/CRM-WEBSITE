# Generated migration to remove masking_id_generated_at and template fields

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('marketing', '0008_job_job_creation_method'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='job',
            name='template',
        ),
        migrations.RemoveField(
            model_name='job',
            name='masking_id_generated_at',
        ),
    ]

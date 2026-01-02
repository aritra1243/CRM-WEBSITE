from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('allocator', '0006_auto_20251129_1342'),
    ]

    operations = [
        migrations.AlterField(
            model_name='job',
            name='status',
            field=models.CharField(choices=[('pending', 'Pending Allocation'), ('allocated', 'Allocated'), ('in_progress', 'In Progress'), ('process', 'Process'), ('close_from_writer', 'Review'), ('active', 'Active'), ('open', 'Open'), ('close', 'Close'), ('hold', 'On Hold'), ('query', 'Query'), ('completed', 'Completed'), ('cancelled', 'Cancelled')], default='pending', max_length=20),
        ),
    ]

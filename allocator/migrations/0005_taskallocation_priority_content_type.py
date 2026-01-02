from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('allocator', '0004_auto_20251122_1536'),
    ]

    operations = [
        migrations.AddField(
            model_name='taskallocation',
            name='content_type',
            field=models.CharField(blank=True, choices=[('content', 'Content'), ('content_creation', 'Content Creation')], max_length=32, null=True),
        ),
        migrations.AddField(
            model_name='taskallocation',
            name='priority',
            field=models.CharField(choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('urgent', 'Urgent')], default='medium', max_length=20),
        ),
    ]

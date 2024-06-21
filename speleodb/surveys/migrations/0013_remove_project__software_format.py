# Generated by Django 5.0.6 on 2024-06-21 03:07

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('surveys', '0012_rename_creation_dt_mutex_creation_date_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='project',
            name='_software',
        ),
        migrations.CreateModel(
            name='Format',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('_format', models.IntegerField(choices=[(0, 'ARIANE'), (1, 'COMPASS'), (2, 'WALLS'), (3, 'STICKMAPS'), (99, 'OTHER')], verbose_name='format')),
                ('creation_date', models.DateTimeField(auto_now_add=True)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rel_formats', to='surveys.project')),
            ],
            options={
                'unique_together': {('project', '_format')},
            },
        ),
    ]
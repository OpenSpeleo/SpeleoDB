# Generated by Django 5.0.6 on 2024-06-05 18:47

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('surveys', '0004_project_country'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveField(
            model_name='project',
            name='mutex_dt',
        ),
        migrations.RemoveField(
            model_name='project',
            name='mutex_owner',
        ),
        migrations.CreateModel(
            name='Mutex',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('creation_dt', models.DateTimeField(auto_now_add=True)),
                ('heartbeat_dt', models.DateTimeField(auto_now=True)),
                ('closing_dt', models.DateTimeField(blank=True, default=None, editable=False, null=True)),
                ('closing_comment', models.TextField(blank=True, default='')),
                ('closing_user', models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.RESTRICT, related_name='rel_closing_mutexes', to=settings.AUTH_USER_MODEL)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rel_mutexes', to='surveys.project')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.RESTRICT, related_name='rel_mutexes', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name_plural': 'mutexes',
            },
        ),
        migrations.AddField(
            model_name='project',
            name='active_mutex',
            field=models.OneToOneField(blank=True, default=None, null=True, on_delete=django.db.models.deletion.RESTRICT, related_name='rel_active_mutexed_project', to='surveys.mutex'),
        ),
    ]

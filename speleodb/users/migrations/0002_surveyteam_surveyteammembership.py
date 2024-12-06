# Generated by Django 5.1.3 on 2024-12-04 03:48

import django.db.models.deletion
import django_countries.fields
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SurveyTeam',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, unique=True)),
                ('description', models.TextField()),
                ('country', django_countries.fields.CountryField(max_length=2)),
                ('creation_date', models.DateTimeField(auto_now_add=True)),
                ('modified_date', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Survey Team',
                'verbose_name_plural': 'Survey Teams',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='SurveyTeamMembership',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_active', models.BooleanField(default=True)),
                ('creation_date', models.DateTimeField(auto_now_add=True)),
                ('modified_date', models.DateTimeField(auto_now=True)),
                ('_role', models.IntegerField(choices=[(0, 'MEMBER'), (1, 'LEADER')], default=0, verbose_name='role')),
                ('deactivated_by', models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.RESTRICT, related_name='rel_deactivated_memberships', to=settings.AUTH_USER_MODEL)),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rel_team_memberships', to='users.surveyteam')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rel_team_memberships', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Survey Team Membership',
                'verbose_name_plural': 'Survey Memberships',
                'unique_together': {('user', 'team')},
            },
        ),
    ]

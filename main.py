#!/usr/bin/env python
# ruff: noqa

import os
import sys
from pathlib import Path
import django
from dotenv import load_dotenv

load_dotenv(".envs/.local/.django")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

# Initialize Django
django.setup()

from pprint import pprint

from speleodb.surveys.models import Project
from speleodb.surveys.models import TeamPermission
from speleodb.surveys.models import UserPermission
from speleodb.users.models import SurveyTeam
from speleodb.users.models import SurveyTeamMembership
from speleodb.users.models import User


if __name__ == "__main__":
    user = User.objects.get(email="contact@speleodb.com")
    print(user)

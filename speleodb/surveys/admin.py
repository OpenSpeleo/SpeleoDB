#!/usr/bin/env python
# -*- coding: utf-8 -*-

# """Admin module for Django."""
from django.contrib import admin

from speleodb.surveys.models import Permission
from speleodb.surveys.models import Project

admin.site.register(Project)
admin.site.register(Permission)

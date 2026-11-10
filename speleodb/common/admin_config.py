"""Select the application's admin site without loading models during app setup."""

from django.contrib.admin.apps import AdminConfig


class SpeleoDBAdminConfig(AdminConfig):
    default_site = "speleodb.common.admin_site.SpeleoDBAdminSite"

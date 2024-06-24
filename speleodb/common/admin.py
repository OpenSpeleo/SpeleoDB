from django.contrib import admin

from speleodb.common.models import Option


# ==================== Option ============================
@admin.register(Option)
class OptionAdmin(admin.ModelAdmin):
    list_display = ("name", "value")
    ordering = ("name",)

    search_fields = ("name",)

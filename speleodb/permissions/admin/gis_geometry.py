from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from speleodb.gis.models import GISGeometry
from speleodb.gis.models import GISGeometryUserPermission

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.http import HttpRequest

    from speleodb.users.models import User


class GISGeometryUserPermissionProxy(GISGeometryUserPermission):
    class Meta:
        proxy = True
        app_label = "permissions"
        verbose_name = "GIS Geometry - User Permission"
        verbose_name_plural = "GIS Geometry - User Permissions"


class GISGeometryPermissionAdminForm(forms.ModelForm):  # type: ignore[type-arg]
    class Meta:
        model = GISGeometryUserPermissionProxy
        fields = ("user", "gis_geometry", "level")

    def clean(self) -> dict[str, Any]:
        data: dict[str, Any] = super().clean() or {}
        geometry: GISGeometry | None = data.get("gis_geometry")
        if geometry is None and not self.instance._state.adding:  # noqa: SLF001
            geometry = self.instance.gis_geometry
        if geometry is not None:
            current = GISGeometry.objects.select_for_update().get(pk=geometry.pk)
            if not current.is_active:
                raise ValidationError(
                    "Access cannot be changed for a deleted geometry."
                )
        return data


@admin.register(GISGeometryUserPermissionProxy)
class GISGeometryUserPermissionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    form = GISGeometryPermissionAdminForm
    list_display = (
        "user",
        "gis_geometry",
        "level_label",
        "is_active",
        "creation_date",
        "modified_date",
        "deactivated_by",
    )
    list_filter = ("is_active", "level", "creation_date", "modified_date")
    search_fields = ("user__email", "user__name", "gis_geometry__name")
    readonly_fields = ("is_active", "deactivated_by", "creation_date", "modified_date")
    ordering = ("-modified_date",)
    actions = ("revoke_access", "restore_access")

    def get_readonly_fields(
        self, request: HttpRequest, obj: GISGeometryUserPermissionProxy | None = None
    ) -> tuple[str, ...]:
        fields = tuple(super().get_readonly_fields(request, obj))
        return (*fields, "user", "gis_geometry") if obj is not None else fields

    def has_delete_permission(
        self, request: HttpRequest, obj: GISGeometryUserPermissionProxy | None = None
    ) -> bool:
        return False

    @transaction.atomic
    def save_model(
        self,
        request: HttpRequest,
        obj: GISGeometryUserPermissionProxy,
        form: forms.ModelForm[GISGeometryUserPermissionProxy],
        change: bool,
    ) -> None:
        geometry = GISGeometry.objects.select_for_update().get(pk=obj.gis_geometry_id)
        if change:
            current = GISGeometryUserPermissionProxy.objects.get(pk=obj.pk)
            obj.is_active = current.is_active
            obj.deactivated_by = current.deactivated_by
        super().save_model(request, obj, form, change)
        geometry.save(update_fields=["modified_date"])

    def _lock_geometries(
        self, queryset: QuerySet[GISGeometryUserPermissionProxy]
    ) -> list[GISGeometry]:
        return list(
            GISGeometry.objects.filter(
                id__in=queryset.values("gis_geometry_id"), is_active=True
            )
            .select_for_update()
            .only("id")
            .order_by("id")
        )

    @admin.action(description="Revoke selected access", permissions=["change"])
    @transaction.atomic
    def revoke_access(
        self, request: HttpRequest, queryset: QuerySet[GISGeometryUserPermissionProxy]
    ) -> None:
        geometries: list[GISGeometry] = self._lock_geometries(queryset)
        timestamp = timezone.now()
        actor: User = request.user  # type: ignore[assignment]
        count: int = queryset.filter(
            gis_geometry__in=geometries, is_active=True
        ).update(is_active=False, deactivated_by=actor, modified_date=timestamp)
        GISGeometry.objects.filter(id__in=[obj.id for obj in geometries]).update(
            modified_date=timestamp
        )
        self.message_user(request, f"Revoked {count} access permissions.")

    @admin.action(description="Restore selected access", permissions=["change"])
    @transaction.atomic
    def restore_access(
        self, request: HttpRequest, queryset: QuerySet[GISGeometryUserPermissionProxy]
    ) -> None:
        geometries: list[GISGeometry] = self._lock_geometries(queryset)
        timestamp = timezone.now()
        count: int = queryset.filter(
            gis_geometry__in=geometries, is_active=False
        ).update(is_active=True, deactivated_by=None, modified_date=timestamp)
        GISGeometry.objects.filter(id__in=[obj.id for obj in geometries]).update(
            modified_date=timestamp
        )
        self.message_user(request, f"Restored {count} access permissions.")

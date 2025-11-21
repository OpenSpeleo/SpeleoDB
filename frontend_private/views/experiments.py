# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect
from django.urls import reverse

from frontend_private.views.base import AuthenticatedTemplateView
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import Experiment
from speleodb.gis.models import ExperimentUserPermission
from speleodb.gis.models.experiment import MandatoryFieldUuid

if TYPE_CHECKING:
    from django.http import HttpResponse
    from django.http.response import HttpResponseRedirectBase

    from speleodb.users.models import User
    from speleodb.utils.requests import AuthenticatedHttpRequest


class ExperimentListingView(AuthenticatedTemplateView):
    template_name = "pages/experiments.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        context = self.get_context_data(**kwargs)

        context["experiment_perms"] = ExperimentUserPermission.objects.filter(
            user=request.user,
            is_active=True,
            experiment__is_active=True,
        ).prefetch_related("experiment")
        return self.render_to_response(context)


class NewExperimentView(AuthenticatedTemplateView):
    template_name = "pages/experiment/new.html"


class _BaseExperimentView(AuthenticatedTemplateView):
    def get_experiment_data(self, user: User, experiment_id: str) -> dict[str, Any]:
        experiment = Experiment.objects.get(id=experiment_id)

        user_perm = ExperimentUserPermission.objects.get(
            user=user,
            experiment=experiment,
            is_active=True,
        )

        # Prepare experiment fields with JSON-serialized options for template
        # Sort by order for display
        experiment_fields_with_json = {}
        if experiment.experiment_fields:
            # Use get_sorted_fields() helper method
            sorted_fields = experiment.get_sorted_fields()
            for field_id, field_data in sorted_fields:
                field_copy = field_data.copy()
                # Serialize options as JSON string for data attribute
                if field_copy.get("options"):
                    field_copy["options_json"] = json.dumps(field_copy["options"])
                # Dict preserves insertion order in Python 3.7+
                experiment_fields_with_json[field_id] = field_copy

        return {
            "experiment": experiment,
            "experiment_fields_with_json": experiment_fields_with_json,
            # "is_experiment_admin": best_permission.level == PermissionLevel.ADMIN,
            "is_experiment_admin": user_perm.level == PermissionLevel.ADMIN,
            # "has_write_access": best_permission.level >= PermissionLevel.READ_AND_WRITE,  # noqa: E501
            "has_write_access": user_perm.level >= PermissionLevel.READ_AND_WRITE,
            "mandatory_field_uuids": MandatoryFieldUuid.get_all_uuids(),
        }


class ExperimentDetailsView(_BaseExperimentView):
    template_name = "pages/experiment/details.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        experiment_id: str,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        try:
            data = self.get_experiment_data(
                user=request.user,
                experiment_id=experiment_id,
            )
        except (ObjectDoesNotExist, PermissionError):
            return redirect(reverse("private:experiments"))

        return super().get(request, *args, **data, **kwargs)


class ExperimentDangerZoneView(_BaseExperimentView):
    template_name = "pages/experiment/danger_zone.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        experiment_id: str,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        try:
            data = self.get_experiment_data(
                user=request.user,
                experiment_id=experiment_id,
            )
        except (ObjectDoesNotExist, PermissionError):
            return redirect(reverse("private:experiments"))

        if not data["is_experiment_admin"]:
            return redirect(
                reverse(
                    "private:experiment_details",
                    kwargs={"experiment_id": experiment_id},
                )
            )

        return super().get(request, *args, **data, **kwargs)


class ExperimentGISView(_BaseExperimentView):
    template_name = "pages/experiment/gis_integration.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        experiment_id: str,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        try:
            data = self.get_experiment_data(
                user=request.user,
                experiment_id=experiment_id,
            )
        except (ObjectDoesNotExist, PermissionError):
            return redirect(reverse("private:experiments"))

        return super().get(request, *args, **data, **kwargs)

    def post(
        self,
        request: AuthenticatedHttpRequest,
        experiment_id: str,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        """Handle refresh token POST request."""
        try:
            data = self.get_experiment_data(
                user=request.user,
                experiment_id=experiment_id,
            )
        except (ObjectDoesNotExist, PermissionError):
            return redirect(reverse("private:experiments"))

        # Only allow admins to refresh the token
        if "_refresh_token" in request.POST:
            if not data.get("is_experiment_admin", False):
                # Redirect back without refreshing if user is not admin
                return redirect(
                    reverse(
                        "private:experiment_gis_integration",
                        kwargs={"experiment_id": experiment_id},
                    )
                )
            experiment = data["experiment"]
            experiment.refresh_gis_token()

        # Redirect back to the same page to show the updated token
        return redirect(
            reverse(
                "private:experiment_gis_integration",
                kwargs={"experiment_id": experiment_id},
            )
        )


class ExperimentUserPermissionsView(_BaseExperimentView):
    template_name = "pages/experiment/user_permissions.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        experiment_id: str,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        try:
            data = self.get_experiment_data(
                user=request.user,
                experiment_id=experiment_id,
            )
        except (ObjectDoesNotExist, PermissionError):
            return redirect(reverse("private:experiments"))

        data["permissions"] = ExperimentUserPermission.objects.filter(
            experiment=data["experiment"], is_active=True
        ).prefetch_related("user")

        return super().get(request, *args, **data, **kwargs)


class ExperimentDataViewerView(_BaseExperimentView):
    template_name = "pages/experiment/data_viewer.html"

    def get(  # type: ignore[override]
        self,
        request: AuthenticatedHttpRequest,
        experiment_id: str,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseRedirectBase | HttpResponse:
        try:
            data = self.get_experiment_data(
                user=request.user,
                experiment_id=experiment_id,
            )
        except (ObjectDoesNotExist, PermissionError):
            return redirect(reverse("private:experiments"))

        return super().get(request, *args, **data, **kwargs)

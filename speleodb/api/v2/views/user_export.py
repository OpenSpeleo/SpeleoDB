# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.db.models import Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse
from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.pagination import PageNumberPagination

from speleodb.api.v2.serializers.user_export import UserExportSerializer
from speleodb.background_jobs.models import ACTIVE_STATES
from speleodb.background_jobs.models import BackgroundJob
from speleodb.background_jobs.services import ExportConflictError
from speleodb.background_jobs.services import ExportExpiredError
from speleodb.background_jobs.services import ExportUnavailableError
from speleodb.background_jobs.services import artifact_download_url
from speleodb.background_jobs.services import request_export
from speleodb.background_jobs.services import retry_export
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from rest_framework.request import Request
    from rest_framework.response import Response


class UserExportPagination(PageNumberPagination):
    page_size = 20


class UserExportBaseView(GenericAPIView[BackgroundJob], SDBAPIViewMixin):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserExportSerializer
    pagination_class = UserExportPagination

    def get_queryset(self) -> QuerySet[BackgroundJob]:
        if getattr(self, "swagger_fake_view", False):
            return BackgroundJob.objects.none()
        return (
            BackgroundJob.objects.filter(requester=self.get_user(), kind="export")
            .select_related("artifact")
            .order_by("-created_at", "-id")
        )

    def conflict_response(self, error: ExportConflictError) -> Response:
        active_job: BackgroundJob | None = (
            self.get_queryset().filter(state__in=ACTIVE_STATES).first()
        )
        return ErrorResponse(
            {
                "detail": str(error),
                "active_job_id": str(active_job.pk) if active_job else None,
            },
            status=status.HTTP_409_CONFLICT,
        )


class UserExportListView(UserExportBaseView):
    def get_queryset(self) -> QuerySet[BackgroundJob]:
        return (
            super()
            .get_queryset()
            .filter(
                Q(state__in=ACTIVE_STATES)
                | Q(artifact__isnull=True)
                | Q(
                    artifact__expires_at__gt=timezone.now(),
                    artifact__deleted_at__isnull=True,
                )
            )
        )

    @extend_schema(responses={200: UserExportSerializer(many=True)})
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        page: Any = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    @extend_schema(request=None, responses={202: UserExportSerializer})
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        try:
            job, _created = request_export(self.get_user())
        except ExportConflictError as error:
            return self.conflict_response(error)
        except ExportUnavailableError as error:
            return ErrorResponse(
                {"detail": str(error)}, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        return SuccessResponse(
            self.get_serializer(job).data, status=status.HTTP_202_ACCEPTED
        )


class UserExportDetailView(UserExportBaseView):
    @extend_schema(responses={200: UserExportSerializer})
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        job: BackgroundJob = get_object_or_404(self.get_queryset(), pk=kwargs["id"])
        return SuccessResponse(self.get_serializer(job).data)


class UserExportRetryView(UserExportBaseView):
    @extend_schema(request=None, responses={202: UserExportSerializer})
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        job: BackgroundJob = get_object_or_404(self.get_queryset(), pk=kwargs["id"])
        try:
            job = retry_export(job, self.get_user())
        except ExportConflictError as error:
            return self.conflict_response(error)
        except ExportUnavailableError as error:
            return ErrorResponse(
                {"detail": str(error)}, status=status.HTTP_409_CONFLICT
            )
        return SuccessResponse(
            self.get_serializer(job).data, status=status.HTTP_202_ACCEPTED
        )


class UserExportDownloadView(UserExportBaseView):
    @extend_schema(
        responses={
            302: OpenApiResponse(description="Redirect to a short-lived S3 URL."),
            409: OpenApiTypes.OBJECT,
            410: OpenApiTypes.OBJECT,
        }
    )
    def get(
        self, request: Request, *args: Any, **kwargs: Any
    ) -> Response | HttpResponseRedirect:
        queryset: QuerySet[BackgroundJob] = self.get_queryset()
        if self.get_user().is_active and self.get_user().is_superuser:
            queryset = BackgroundJob.objects.filter(kind="export").select_related(
                "artifact"
            )
        job: BackgroundJob = get_object_or_404(queryset, pk=kwargs["id"])
        try:
            url: str = artifact_download_url(job, self.get_user())
        except ExportExpiredError as error:
            return ErrorResponse({"detail": str(error)}, status=status.HTTP_410_GONE)
        except ExportUnavailableError as error:
            return ErrorResponse(
                {"detail": str(error)}, status=status.HTTP_409_CONFLICT
            )
        response: HttpResponseRedirect = HttpResponseRedirect(url)
        response["Cache-Control"] = "private, no-store"
        response["Referrer-Policy"] = "no-referrer"
        return response

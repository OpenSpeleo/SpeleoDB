# -*- coding: utf-8 -*-

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

from django.conf import settings
from django.core.files.storage import default_storage
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.parsers import FormParser
from rest_framework.parsers import JSONParser
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from speleodb.api.v1.permissions import UserHasReadAccess
from speleodb.api.v1.permissions import UserHasWriteAccess
from speleodb.surveys.models import Project
from speleodb.surveys.models.station import StationResource
from speleodb.utils.api_mixin import SDBAPIViewMixin
from speleodb.utils.response import ErrorResponse
from speleodb.utils.response import SuccessResponse

if TYPE_CHECKING:
    from rest_framework.request import Request


class MediaPresignedUploadView(GenericAPIView[Any], SDBAPIViewMixin):
    """
    Handle file uploads - supports both direct upload and S3 presigned URLs.
    """

    permission_classes = [UserHasWriteAccess]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request: Request) -> Response:
        """Handle file upload or generate presigned URL."""
        # Check if this is a direct file upload
        if "file" in request.FILES:
            return self._handle_direct_upload(request)
        return self._handle_presigned_url(request)

    def _handle_direct_upload(self, request: Request) -> Response:
        """Handle direct file upload."""
        file = request.FILES.get("file")
        resource_type = request.data.get("resource_type", "document")

        if not file:
            return ErrorResponse(
                {"error": "file is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate resource type
        valid_types = ["photo", "video", "document", "sketch", "note"]
        if resource_type not in valid_types:
            return ErrorResponse(
                {"error": f"invalid resource_type. Must be one of: {valid_types}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Generate unique filename
            file_extension = Path(file.name).suffix if file.name else ""
            unique_filename = f"{uuid.uuid4().hex}{file_extension}"

            # Create storage path
            from datetime import datetime

            now = datetime.now()
            file_path = f"stations/resources/{now.year:04d}/{now.month:02d}/{now.day:02d}/{unique_filename}"

            # Save file using Django's storage system
            saved_path = default_storage.save(file_path, file)

            # Generate file URL
            file_url = default_storage.url(saved_path)

            # Calculate file hash for integrity
            file.seek(0)  # Reset file pointer
            file_hash = hashlib.sha256(file.read()).hexdigest()

            return SuccessResponse(
                {
                    "file_path": saved_path,
                    "file_url": file_url,
                    "file_size": file.size,
                    "file_hash": file_hash,
                    "content_type": file.content_type,
                    "original_filename": file.name,
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            return ErrorResponse(
                {"error": f"Upload failed: {e!s}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _handle_presigned_url(self, request: Request) -> Response:
        """Generate presigned URL for S3 upload."""
        if not getattr(settings, "USE_S3", False):
            return ErrorResponse(
                {"error": "Presigned URLs require S3 storage to be enabled"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get request parameters
        filename = request.data.get("filename")
        content_type = request.data.get("content_type", "application/octet-stream")
        resource_type = request.data.get("resource_type", "document")

        if not filename:
            return ErrorResponse(
                {"error": "filename is required for presigned URL"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            import boto3
            from botocore.exceptions import ClientError

            # Generate unique filename
            unique_filename = f"{uuid.uuid4().hex}_{filename}"
            key = f"stations/resources/{unique_filename}"

            # Create storage client
            s3_client = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME,
            )

            # Generate presigned URL for upload (valid for 15 minutes)
            presigned_url = s3_client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
                    "Key": key,
                    "ContentType": content_type,
                    "Metadata": {
                        "uploaded-by": str(request.user.id),
                        "resource-type": resource_type,
                    },
                },
                ExpiresIn=900,  # 15 minutes
            )

            return SuccessResponse(
                {
                    "upload_url": presigned_url,
                    "file_key": key,
                    "expires_in": 900,
                    "instructions": {
                        "method": "PUT",
                        "headers": {
                            "Content-Type": content_type,
                        },
                        "note": "Upload the file using PUT request to upload_url",
                    },
                }
            )

        except ClientError as e:
            return ErrorResponse(
                {"error": f"Failed to generate upload URL: {e!s}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            return ErrorResponse(
                {"error": f"Unexpected error: {e!s}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class MediaSignedUrlView(GenericAPIView[Any], SDBAPIViewMixin):
    """
    Generate signed URLs for downloading files.
    """

    permission_classes = [UserHasWriteAccess]

    def post(self, request: Request) -> Response:
        """Generate a signed URL for file download."""
        if not getattr(settings, "USE_S3", False):
            return ErrorResponse(
                {"error": "Signed URLs require S3 storage to be enabled"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get request parameters
        file_key = request.data.get("file_key")
        expires_in = request.data.get("expires_in", 3600)  # Default 1 hour

        if not file_key:
            return ErrorResponse(
                {"error": "file_key is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            import boto3
            from botocore.exceptions import ClientError

            # Create storage client
            s3_client = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME,
            )

            # Generate signed URL for download
            signed_url = s3_client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
                    "Key": file_key,
                },
                ExpiresIn=expires_in,
            )

            return SuccessResponse(
                {
                    "download_url": signed_url,
                    "expires_in": expires_in,
                    "file_key": file_key,
                }
            )

        except ClientError as e:
            return ErrorResponse(
                {"error": f"Failed to generate download URL: {e!s}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            return ErrorResponse(
                {"error": f"Unexpected error: {e!s}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class MediaSecureAccessView(GenericAPIView[Any], SDBAPIViewMixin):
    """
    Generate secure access URLs for private files.
    Supports both resource_id (for existing resources) and file_path+project_id (for general access).
    """

    permission_classes = [UserHasReadAccess]

    def post(self, request: Request) -> Response:
        """Generate a secure access URL for file viewing/download."""
        # Support both old format (resource_id) and new format (file_path + project_id)
        resource_id = request.data.get("resource_id")
        file_path = request.data.get("file_path")
        project_id = request.data.get("project_id")
        expires_in = min(int(request.data.get("expires_in", 3600)), 3600)  # Max 1 hour

        if resource_id:
            return self._handle_resource_access(request, resource_id, expires_in)
        if file_path and project_id:
            return self._handle_file_path_access(
                request, file_path, project_id, expires_in
            )
        return ErrorResponse(
            {"error": "Either resource_id OR (file_path + project_id) is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def _handle_resource_access(
        self, request: Request, resource_id: str, expires_in: int
    ) -> Response:
        """Handle access by resource ID."""
        try:
            resource = get_object_or_404(StationResource, id=resource_id)

            # Check if user has access to this resource's project
            project = resource.station.project
            try:
                user_permission = project.get_user_permission(user=request.user)
                if (
                    user_permission.level
                    < project.get_user_permission(user=request.user).level
                ):
                    return ErrorResponse(
                        {"error": "You don't have permission to access this resource"},
                        status=status.HTTP_403_FORBIDDEN,
                    )
            except Exception:
                return ErrorResponse(
                    {"error": "You don't have permission to access this resource"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Generate access URL for the specific file
            if not resource.file:
                return ErrorResponse(
                    {"error": "Resource has no file attached"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            if getattr(settings, "USE_S3", False):
                return self._generate_s3_url(resource.file.name, expires_in)
            return self._generate_local_url(resource.file.name)

        except StationResource.DoesNotExist:
            return ErrorResponse(
                {"error": "Resource not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

    def _handle_file_path_access(
        self, request: Request, file_path: str, project_id: str, expires_in: int
    ) -> Response:
        """Handle access by file path and project ID."""
        # Validate path to prevent directory traversal
        if ".." in file_path or file_path.startswith("/"):
            return ErrorResponse(
                {"error": "Invalid file path"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            project = get_object_or_404(Project, id=project_id)

            # Check if user has access to this project
            try:
                user_permission = project.get_user_permission(user=request.user)
                # Any read access is sufficient for file access
            except Exception:
                return ErrorResponse(
                    {
                        "error": "You don't have permission to access files in this project"
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Check if file exists
            if not default_storage.exists(file_path):
                return ErrorResponse(
                    {"error": "File not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            if getattr(settings, "USE_S3", False):
                return self._generate_s3_url(file_path, expires_in)
            return self._generate_local_url(file_path)

        except Project.DoesNotExist:
            return ErrorResponse(
                {"error": "Project not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

    def _generate_s3_url(self, file_path: str, expires_in: int) -> Response:
        """Generate S3 presigned URL."""
        try:
            import boto3
            from botocore.exceptions import ClientError

            # Create storage client
            s3_client = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME,
            )

            # Generate secure access URL
            access_url = s3_client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
                    "Key": file_path,
                },
                ExpiresIn=expires_in,
            )

            return SuccessResponse(
                {
                    "access_url": access_url,
                    "expires_in": expires_in,
                    "file_path": file_path,
                    "security_note": "This URL is temporary and expires automatically",
                }
            )

        except ClientError as e:
            return ErrorResponse(
                {"error": f"Failed to generate access URL: {e!s}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _generate_local_url(self, file_path: str) -> Response:
        """Generate local file URL."""
        try:
            # For local storage, return the file URL directly
            file_url = default_storage.url(file_path)

            return SuccessResponse(
                {
                    "access_url": file_url,
                    "expires_in": None,  # Local URLs don't expire
                    "file_path": file_path,
                    "security_note": "Local file access - ensure proper server configuration for security",
                }
            )

        except Exception as e:
            return ErrorResponse(
                {"error": f"Failed to generate local URL: {e!s}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

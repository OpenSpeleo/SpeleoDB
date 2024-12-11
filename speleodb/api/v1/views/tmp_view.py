import os
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.http import JsonResponse
from django.utils.html import escape
from django.views import View
from rest_framework import status

# class FileUploadView(View):
#     def post(self, request):
#         # Check if the request contains files
#         uploaded_files = request.FILES.getlist("files[]")
#         if not uploaded_files:
#             return JsonResponse({"error": "No files were uploaded."}, status=400)
#         if len(uploaded_files) > 20:  # noqa: PLR2004
#             return JsonResponse(
#                 {"error": "You can upload a maximum of 20 files."}, status=400
#             )
#         stored_files = []
#         fs = FileSystemStorage(location=Path(settings.BASE_DIR) / "tmp_upload")
#         for file in uploaded_files:
#             # Sanitize filename
#             filename = fs.get_available_name(escape(file.name))
#             # Limit file size (e.g., 10 MB max)
#             if file.size > 10 * 1024 * 1024:
#                 return JsonResponse(
#                     {"error": f"File {filename} exceeds the size limit."}, status=400
#                 )
#             # Save file
#             saved_file_path = fs.save(filename, file)
#             stored_files.append(fs.url(saved_file_path))
#         return JsonResponse({"files": stored_files}, status=200)
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

# from .serializers import FileUploadSerializer


class FileUploadView(GenericAPIView):
    pass

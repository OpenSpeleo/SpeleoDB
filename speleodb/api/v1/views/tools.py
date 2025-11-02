# -*- coding: utf-8 -*-
from __future__ import annotations

import io
import logging
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

from django.core.exceptions import ValidationError
from mnemo_lib.models import DMPFile
from pydantic import ValidationError as PydanticValidationError
from rest_framework import permissions
from rest_framework import status
from rest_framework.views import APIView

from speleodb.api.v1.views.tmp_utils import SurveyData
from speleodb.utils.response import DownloadResponseFromBlob
from speleodb.utils.response import ErrorResponse

if TYPE_CHECKING:
    from django.http import FileResponse
    from rest_framework.request import Request
    from rest_framework.response import Response


logger = logging.getLogger(__name__)


class ToolXLSToDMP(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(
        self, request: Request, *args: Any, **kwargs: Any
    ) -> Response | FileResponse:
        survey_unit = request.data["unit"]

        def format_float(val: str | None) -> float:
            if val is None or val == "":
                return 0.0

            value = float(val)  # pyright: ignore[reportAssignmentType]
            if survey_unit == "feet":
                value /= 3.28084

            return round(value, 2)

        try:
            survey_data = {
                "date": f"{request.data['survey_date']} 00:00",
                "direction": 0
                if request.data["direction"] == "in"
                else 1,  # In: 0, Out: 1
                "name": "AA1",
                "shots": [
                    {
                        "depth_in": format_float(shot_data["depth"]),
                        "depth_out": format_float(shot_data["depth"]),
                        "down": format_float(shot_data["down"]),
                        "head_in": round(float(shot_data["azimuth"])),
                        "head_out": round(float(shot_data["azimuth"])),
                        "hours": 0,
                        "left": format_float(shot_data["left"]),
                        "length": format_float(shot_data["length"]),
                        "marker_idx": 0,
                        "minutes": 0,
                        "pitch_in": 0,
                        "pitch_out": 0,
                        "right": format_float(shot_data["right"]),
                        "seconds": 0,
                        "temperature": 0,
                        "type": 2,  # TypeShot: 0:CSA, 1: CSB, 2: STD, 3: EOL
                        "up": format_float(shot_data["up"]),
                    }
                    for shot_data in request.data["shots"]
                ],
                "version": 5,
            }

            # Adding the EOL shot
            survey_data["shots"].append(  # type: ignore[union-attr]
                {
                    "depth_in": 0.0,
                    "depth_out": 0.0,
                    "down": 0.0,
                    "head_in": 0.0,
                    "head_out": 0.0,
                    "hours": 0,
                    "left": 0.0,
                    "length": 0.0,
                    "marker_idx": 0,
                    "minutes": 0,
                    "pitch_in": 0.0,
                    "pitch_out": 0.0,
                    "right": 0.0,
                    "seconds": 0,
                    "temperature": 0.0,
                    "type": 3,  # TypeShot: 0:CSA, 1: CSB, 2: STD, 3: EOL
                    "up": 0.0,
                }
            )

            dmp_obj = DMPFile.model_validate([survey_data])

        except (ValueError, ValidationError) as e:
            return ErrorResponse({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        obj_stream = io.BytesIO()
        with tempfile.TemporaryDirectory() as tmpdir:
            dmp_file = Path(tmpdir) / "survey.dmp"
            dmp_obj.to_dmp(dmp_file)

            with dmp_file.open(mode="rb") as f:
                # Copy the contents from the source file to the destination stream
                shutil.copyfileobj(f, obj_stream)
                obj_stream.seek(0)  # Reset stream position to the beginning

        return DownloadResponseFromBlob(
            obj=obj_stream, filename=dmp_file.name, attachment=True
        )


def format_pydantic_error(err: PydanticValidationError) -> str:
    """
    Convert a Pydantic ValidationError into a nicely formatted string.
    """
    messages: list[str] = []
    for e in err.errors():
        loc = " → ".join(str(x) for x in e["loc"])
        msg = e["msg"]
        typ = e["type"]
        return f'- [{typ}] "{loc}": {msg}'
    return "\n".join(messages)


class ToolXLSToCompass(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(
        self, request: Request, *args: Any, **kwargs: Any
    ) -> Response | FileResponse:
        try:
            compass_survey = SurveyData.model_validate(request.data)
            buffer = compass_survey.export_to_dat_format()
        except (ValueError, PydanticValidationError) as exc:
            error = (
                format_pydantic_error(exc)
                if isinstance(exc, PydanticValidationError)
                else str(exc)
            )
            return ErrorResponse({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        # Convert StringIO → BytesIO
        bytes_io = io.BytesIO(buffer.getvalue().encode("utf-8"))
        bytes_io.seek(0)

        return DownloadResponseFromBlob(
            obj=bytes_io,
            filename="survey.dat",
            attachment=True,
        )


class ToolDMP2JSON(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(
        self, request: Request, *args: Any, **kwargs: Any
    ) -> Response | FileResponse:
        try:
            # Get the uploaded file
            if "file" not in request.FILES:
                return ErrorResponse(
                    {"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST
                )

            uploaded_file = request.FILES["file"]

            # Validate file extension
            if not uploaded_file.name.lower().endswith(".dmp"):
                return ErrorResponse(
                    {"error": "Invalid file type. Only .dmp files are allowed"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Save to temporary file and parse
            with tempfile.TemporaryDirectory() as tmpdir:
                dmp_file_path = Path(tmpdir) / uploaded_file.name

                # Write uploaded file to disk
                with dmp_file_path.open("wb") as f:
                    for chunk in uploaded_file.chunks():
                        f.write(chunk)

                # Parse DMP file
                dmp_obj = DMPFile.from_dmp(dmp_file_path)

        except (ValueError, ValidationError, PydanticValidationError) as exc:
            error = (
                format_pydantic_error(exc)
                if isinstance(exc, PydanticValidationError)
                else str(exc)
            )
            return ErrorResponse({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as exc:
            logger.exception("Error converting DMP to JSON")
            return ErrorResponse(
                {"error": f"Failed to parse DMP file: {exc!s}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Convert StringIO → BytesIO
        bytes_io = io.BytesIO(dmp_obj.model_dump_json(indent=4).encode("utf-8"))
        bytes_io.seek(0)

        return DownloadResponseFromBlob(
            obj=bytes_io,
            filename="survey.dat",
            attachment=True,
        )

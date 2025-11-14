# -*- coding: utf-8 -*-
from __future__ import annotations

import io
import json
import logging
import shutil
import tempfile
from itertools import pairwise
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Annotated
from typing import Any
from typing import Literal

from django.core.exceptions import ValidationError
from mnemo_lib.commands.correct import correct as correct_dmp_cmd
from mnemo_lib.constants import ShotType
from mnemo_lib.constants import SurveyDirection
from mnemo_lib.models import DMPFile
from pydantic import BaseModel
from pydantic import Field
from pydantic import PastDate
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
            survey_data: dict[str, Any] = {
                "date": f"{request.data['survey_date']} 00:00",
                "direction": (
                    SurveyDirection.IN
                    if request.data["direction"] == "in"
                    else SurveyDirection.OUT
                ),
                "name": "AA1",
                "version": 5,
            }

            shots: list[dict[str, Any]] = []
            for shot_data_start, shot_data_end in pairwise(request.data["shots"]):
                shots.append(
                    {
                        "depth_in": format_float(shot_data_start["depth"]),
                        "depth_out": format_float(shot_data_end["depth"]),
                        "down": format_float(shot_data_start["down"]),
                        "head_in": round(float(shot_data_start["azimuth"]), 2),
                        "head_out": round(float(shot_data_start["azimuth"]), 2),
                        "hours": 0,
                        "left": format_float(shot_data_start["left"]),
                        "length": format_float(shot_data_start["length"]),
                        "marker_idx": 0,
                        "minutes": 0,
                        "pitch_in": 0,
                        "pitch_out": 0,
                        "right": format_float(shot_data_start["right"]),
                        "seconds": 0,
                        "temperature": 0,
                        "type": ShotType.STANDARD,
                        "up": format_float(shot_data_start["up"]),
                    }
                )

            # Adding the EOL shot
            shots.append(
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
                    "type": ShotType.END_OF_SURVEY,
                    "up": 0.0,
                }
            )

            survey_data["shots"] = shots

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

            if uploaded_file.size == 0:
                return ErrorResponse(
                    {"error": "The uploaded file is empty"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

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
            return ErrorResponse(
                {"error": f"The DMP file seems invalid: {error}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

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


class DMPDoctorQuery(BaseModel):
    fix_dmp: bool

    survey_date: PastDate | None

    length_scaling: Annotated[float, Field(gt=0)]

    compass_offset: Annotated[int, Field(gt=-360, lt=360)]
    reverse_direction: bool

    depth_offset: Annotated[float, Field(gt=-300, lt=300)]
    depth_offset_unit: Literal["feet", "meters"]


class ToolDMPDoctor(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(
        self, request: Request, *args: Any, **kwargs: Any
    ) -> Response | FileResponse:
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

        # Parse JSON data from the 'data' field

        try:
            data = json.loads(request.data.get("data", {}))
        except json.JSONDecodeError:
            return ErrorResponse(
                {"error": "Invalid data format"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            params = DMPDoctorQuery.model_validate(data)
        except (ValueError, PydanticValidationError) as exc:
            error = (
                format_pydantic_error(exc)
                if isinstance(exc, PydanticValidationError)
                else str(exc)
            )
            return ErrorResponse({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        obj_stream = io.BytesIO()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "output.dmp"

            if params.fix_dmp:
                if params.survey_date is None:
                    return ErrorResponse(
                        {"error": "`survey_date` is necessary to fix a DMP file."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                content: str = uploaded_file.read().decode("utf-8")
                dmp_data = [int(v) for v in content.split(";") if v]

                _ = DMPFile.from_dmp_data(
                    dmp_data,
                    uncorrupt=True,
                    uncorrupt_date=params.survey_date,
                ).to_dmp(output_file)

            else:
                input_file = Path(tmpdir) / "input.dmp"

                # Write uploaded file to disk
                with input_file.open("wb") as f:
                    for chunk in uploaded_file.chunks():
                        f.write(chunk)

                flags = [
                    "--input_file",
                    str(input_file.resolve()),
                    "--output_file",
                    str(output_file.resolve()),
                ]

                if params.survey_date:
                    flags.extend(["--date", params.survey_date.strftime("%Y-%m-%d")])

                if params.length_scaling != 1.0:
                    flags.extend(["--length_scaling", str(params.length_scaling)])

                if params.depth_offset != 0.0:
                    flags.extend(
                        [
                            "--depth_offset",
                            str(params.depth_offset)
                            if params.depth_offset_unit == "meters"
                            else str(params.depth_offset * 0.3048),
                        ]
                    )

                if params.reverse_direction:
                    flags.append("--reverse_azimuth")
                elif params.compass_offset != 0:
                    flags.extend(["--compass_offset", str(params.compass_offset % 360)])

                try:
                    assert correct_dmp_cmd(flags) == 0

                except Exception as e:  # noqa: BLE001
                    return ErrorResponse(
                        {"error": f"Unexpected behavior: {e}"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            with output_file.open(mode="rb") as f:
                # Copy the contents from the source file to the destination stream
                shutil.copyfileobj(f, obj_stream)
                obj_stream.seek(0)  # Reset stream position to the beginning

        return DownloadResponseFromBlob(
            obj=obj_stream,
            filename="survey.dat",
            attachment=True,
        )

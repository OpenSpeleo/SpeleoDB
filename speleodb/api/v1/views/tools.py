# -*- coding: utf-8 -*-# -*- coding: utf-8 -*-

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
from rest_framework import permissions
from rest_framework import status
from rest_framework.views import APIView

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
                        "depth_in": format_float(shot_data["Depth"]),
                        "depth_out": format_float(shot_data["Depth"]),
                        "down": format_float(shot_data["Down"]),
                        "head_in": round(float(shot_data["Azimuth"])),
                        "head_out": round(float(shot_data["Azimuth"])),
                        "hours": 0,
                        "left": format_float(shot_data["Left"]),
                        "length": format_float(shot_data["Length"]),
                        "marker_idx": 0,
                        "minutes": 0,
                        "pitch_in": 0,
                        "pitch_out": 0,
                        "right": format_float(shot_data["Right"]),
                        "seconds": 0,
                        "temperature": 0,
                        "type": 2,  # TypeShot: 0:CSA, 1: CSB, 2: STD, 3: EOL
                        "up": format_float(shot_data["Up"]),
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

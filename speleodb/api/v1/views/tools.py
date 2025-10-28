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
from rest_framework import permissions
from rest_framework import status
from rest_framework.views import APIView

from speleodb.utils.response import DownloadResponseFromBlob
from speleodb.utils.response import ErrorResponse

if TYPE_CHECKING:
    from django.http import FileResponse
    from rest_framework.request import Request
    from rest_framework.response import Response

# ruff: noqa: E501


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


class ToolXLSToCompass(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(
        self, request: Request, *args: Any, **kwargs: Any
    ) -> Response | FileResponse:
        obj_stream = io.BytesIO()
        obj_stream.write(b"""Fulford Cave
SURVEY NAME: SS
SURVEY DATE: 8 28 1988  COMMENT:Surface to shelter
SURVEY TEAM:
Mike Roberts,Ken Kreager,Rick Rhinehart, ,
DECLINATION:   11.18  FORMAT: DDDDUDLRLADN  CORRECTIONS:  0.00 0.00 0.00

        FROM           TO   LENGTH  BEARING      INC     LEFT       UP     DOWN    RIGHT   FLAGS  COMMENTS

          A1          SS1    62.45   104.00    34.50 -9999.00 -9999.00 -9999.00 -9999.00  #|P#
         SS1          SS2    35.35   120.50    22.00 -9999.00 -9999.00 -9999.00 -9999.00  #|P#
         SS2          SS3    25.35   150.50    10.50 -9999.00 -9999.00 -9999.00 -9999.00  #|P#
         SS3          SS4    67.20   117.00    29.50 -9999.00 -9999.00 -9999.00 -9999.00  #|P#
         SS4          SS5    60.10   123.50    16.00 -9999.00 -9999.00 -9999.00 -9999.00  #|P#
         SS5          SS6    54.50   112.00    11.00 -9999.00 -9999.00 -9999.00 -9999.00  #|P#
         SS6          SS7    36.30    89.00    21.00 -9999.00 -9999.00 -9999.00 -9999.00
         SS6          SS8    41.70   333.50    -2.50 -9999.00 -9999.00 -9999.00 -9999.00
\f""")

        obj_stream.seek(0)

        return DownloadResponseFromBlob(
            obj=obj_stream, filename="survey.dat", attachment=True
        )

        # return Response(status=status.HTTP_200_OK)

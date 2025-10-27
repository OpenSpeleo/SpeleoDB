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
from django.utils import timezone
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
        dt_now = timezone.now()

        try:
            survey_data = {
                "date": dt_now.strftime("%Y-%m-%d %H:%M"),
                "direction": 1,
                "name": "AA1",
                "shots": [
                    {
                        "depth_in": 0,
                        "depth_out": float(shot_data["Depth"]),
                        "down": float(shot_data["Down"]) if shot_data["Down"] else 0,
                        "head_in": float(shot_data["Azimuth"]),
                        "head_out": float(shot_data["Azimuth"]),
                        "hours": dt_now.hour,
                        "left": float(shot_data["Left"]) if shot_data["Left"] else 0,
                        "length": float(shot_data["Length"]),
                        "marker_idx": 0,
                        "minutes": dt_now.minute,
                        "pitch_in": 0,
                        "pitch_out": 0,
                        "right": float(shot_data["Right"]) if shot_data["Right"] else 0,
                        "seconds": dt_now.second,
                        "temperature": 0,
                        "type": 2,  # TypeShot: 0:CSA, 1: CSB, 2: STD, 3: EOL
                        "up": float(shot_data["Up"]) if shot_data["Up"] else 0,
                    }
                    for shot_data in request.data["shots"]
                ],
                "version": 5,
            }

            # Adding the EOL shot
            survey_data["shots"].append(  # type: ignore[attr-defined]
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
        )  # pyright: ignore[reportReturnType]

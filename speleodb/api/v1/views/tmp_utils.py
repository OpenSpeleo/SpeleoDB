from __future__ import annotations

import io
import math
from datetime import datetime
from itertools import pairwise
from typing import TYPE_CHECKING

import pyIGRF14 as pyIGRF
from compass_lib.constants import COMPASS_SECTION_SEPARATOR
from compass_lib.enums import ShotFlag
from openspeleo_lib.geo_utils import decimal_year
from pydantic import BaseModel
from pydantic import Field
from pydantic import PastDate
from pydantic import field_validator
from pydantic import model_validator

if TYPE_CHECKING:
    from typing import Any
    from typing import Self


def calc_inclination(length: float, delta_depth: float) -> float:
    """
    Calculate inclination (in degrees) given shot length and delta depth.

    Compass Convention:
    - Positive: Going Up/Shallower (delta_depth < 0)
    - Negative: Going Down/Deeper (delta_depth > 0)
    """
    if abs(delta_depth) > length:
        raise ValueError("Delta depth cannot be greater than shot length.")

    if length == 0.0:
        raise ValueError("Impossible to calculate inclination of a zero-length shot.")

    # Calculate inclination in radians
    theta_rad = math.asin(delta_depth / length)

    # Convert to degrees
    return -round(math.degrees(theta_rad), 2)


class BaseShot(BaseModel):
    # LRUD
    left: float | None = None
    right: float | None = None
    up: float | None = None
    down: float | None = None

    flags: str | None = Field(None, max_length=64)
    comment: str | None = Field(None, max_length=256)

    # Convert stringified numbers to floats
    @field_validator("left", "right", "up", "down", mode="before")
    @classmethod
    def parse_numeric_str(cls, v: Any) -> float | None:
        if v in ("", None):
            return None

        try:
            return float(v)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Expected numeric or empty value, got {v!r}") from e

    @model_validator(mode="after")
    def check_measurements(self) -> Self:
        # Ensure Left/Right/Up/Down are non-negative if present
        for field_name in ("left", "right", "up", "down"):
            value = getattr(self, field_name)
            if value is not None and value < 0:
                raise ValueError(f"{field_name} cannot be negative")

        return self

    @model_validator(mode="after")
    def validate_model(self) -> Self:
        return self


class InputShot(BaseShot):
    station: str = Field(..., min_length=1, max_length=32)

    azimuth: float | str | None = Field(
        ..., ge=0, lt=360, description="Bearing in degrees [0-360)"
    )
    depth: float = Field(..., description="Depth change (positive = down)")
    length: float | str | None = Field(
        ..., gt=0, description="Shot length in unit system"
    )

    _ = field_validator("azimuth", "depth", "length", mode="before")(
        BaseShot.parse_numeric_str
    )


class CompassShot(BaseShot):
    from_: str = Field(..., min_length=1, max_length=32)
    to: str = Field(..., min_length=1, max_length=32)

    azimuth: float = Field(..., ge=0, lt=360, description="Bearing in degrees [0-360)")
    inclination: float = Field(..., ge=-90.0, le=90.0)
    length: float = Field(..., gt=0, description="Shot length in unit system")

    _ = field_validator("azimuth", "inclination", "length", mode="before")(
        BaseShot.parse_numeric_str
    )


class DeclinationObj(BaseModel):
    survey_date: PastDate
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)

    @property
    def declination(self) -> float:
        declination: float = pyIGRF.igrf_value(  # type: ignore[attr-defined,no-untyped-call]
            self.latitude,
            self.longitude,
            alt=0.0,
            year=decimal_year(datetime.combine(self.survey_date, datetime.min.time())),
        )[0]
        return round(declination, 2)


class SurveyData(BaseModel):
    cave_name: str = Field(..., min_length=1, max_length=64)
    survey_name: str = Field(..., min_length=1, max_length=64)
    survey_date: PastDate

    survey_team: list[str] = Field(..., min_length=0)

    unit: str = Field(..., pattern=r"^(feet|meters)$", description="Supported units")
    comment: str | None = Field(None, max_length=512)
    declination: float = Field(..., ge=-90.0, le=90.0)

    shots: list[CompassShot] = Field(..., min_length=1)

    @field_validator("survey_team")
    @classmethod
    def strip_team_names(cls, v: list[str]) -> list[str]:
        return [name.strip() for name in v if name.strip()]

    @model_validator(mode="before")
    @classmethod
    def validate_model(cls, data: dict[str, Any]) -> dict[str, Any]:
        shots: list[dict[str, Any]] | None = data.pop("shots", None)
        if shots is None or not len(shots):
            raise ValueError("No shot data received ...")

        if len(shots) < 2:  # noqa: PLR2004
            raise ValueError(
                "A minimum of 2 entries must be received. Only 1 received ..."
            )

        processed_shots: list[InputShot] = [
            InputShot.model_validate(shot) for shot in shots
        ]

        # The last shot should only contain: `station` and `depth` - no length/azimuth/LRUD/flags/comment  # noqa: E501
        last_shot = processed_shots[-1]
        for key in [
            # Core
            "azimuth",
            "length",
            # LRUD
            "left",
            "right",
            "up",
            "down",
            # Extra
            "flags",
            "comment",
        ]:
            if val := getattr(last_shot, key):
                raise ValueError(
                    f"The last shot can not contain any value for `{key}`, "
                    f"received: {val}."
                )

        output_shots: list[CompassShot] = []
        for station_start, station_end in pairwise(processed_shots):
            delta_depth = station_end.depth - station_start.depth

            try:
                shot_length = float(station_start.length)  # type: ignore[arg-type]
            except TypeError as e:
                raise ValueError(
                    f"Shot `{station_start.station}` must have length defined."
                ) from e

            if abs(delta_depth) > shot_length:
                raise ValueError(
                    f"Shot `{station_start.station}` has an invalid length."
                    f"\n\t- Length: {shot_length}"
                    f"\n\t- Delta Depth: {delta_depth}"
                )

            inclination = calc_inclination(
                length=shot_length,
                delta_depth=delta_depth,
            )

            output_shots.append(
                CompassShot(
                    from_=station_start.station,
                    to=station_end.station,
                    # Core
                    length=shot_length,
                    inclination=inclination,
                    azimuth=station_start.azimuth,  # type: ignore[arg-type]
                    # LRUD
                    left=station_start.left,
                    right=station_start.right,
                    up=station_start.up,
                    down=station_start.down,
                    # extra
                    flags=station_start.flags.lstrip(ShotFlag.__start_token__).rstrip(
                        ShotFlag.__end_token__
                    )
                    if isinstance(station_start.flags, str)
                    else None,
                    comment=station_start.comment,
                )
            )
        data["shots"] = [shot.model_dump() for shot in output_shots]

        data["declination"] = DeclinationObj(
            survey_date=data["survey_date"],
            longitude=data.pop("longitude"),
            latitude=data.pop("latitude"),
        ).declination

        return data

    @property
    def survey_format(self) -> str:
        return "DDDDUDLRLADN"

    @property
    def correction(self) -> list[float]:
        return [0.00, 0.00, 0.00]

    @property
    def correction2(self) -> list[float]:
        return [0.00, 0.00]

    def export_to_dat_format(self) -> io.StringIO:
        buffer = io.StringIO()

        # Section Header
        buffer.write(f"{self.cave_name}\n")
        buffer.write(f"SURVEY NAME: {self.survey_name.replace(" ", "_")}\n")
        buffer.write(f"SURVEY DATE: {self.survey_date.strftime('%m %-d %Y')}\n")
        buffer.write(f"COMMENT: {self.comment}\n")
        buffer.write(f"SURVEY TEAM:\n{', '.join(self.survey_team)}\n")
        buffer.write(f"DECLINATION: {self.declination:>7.02f}  ")
        buffer.write("FORMAT: DDDDUDLRLADN  ")
        buffer.write(
            f"CORRECTIONS:  {' '.join(f'{nbr:.02f}' for nbr in self.correction)}  "
        )
        buffer.write(
            f"CORRECTIONS2:  {' '.join(f'{nbr:.02f}' for nbr in self.correction2)}\n\n"
        )

        # Shots - Header
        buffer.write("        FROM           TO   LENGTH  BEARING      INC")
        buffer.write("     LEFT       UP     DOWN    RIGHT   FLAGS  COMMENTS\n\n")

        # Shots - Data
        for shot in self.shots:
            buffer.write(f"{shot.from_: >12} ")
            buffer.write(f"{shot.to: >12} ")
            buffer.write(f"{shot.length:8.2f} ")
            buffer.write(f"{shot.azimuth:8.2f} ")
            buffer.write(f"{shot.inclination:8.2f} ")
            buffer.write(f"{shot.left if shot.left is not None else -9999:8.2f} ")
            buffer.write(f"{shot.up if shot.up is not None else -9999:8.2f} ")
            buffer.write(f"{shot.down if shot.down is not None else -9999:8.2f} ")
            buffer.write(f"{shot.right if shot.right is not None else -9999:8.2f} ")
            if shot.flags is not None and shot.flags != "":
                escaped_start_token = str(ShotFlag.__start_token__).replace("\\", "")
                buffer.write(
                    f" {escaped_start_token}{shot.flags}{ShotFlag.__end_token__}"
                )
            if shot.comment is not None:
                buffer.write(f" {shot.comment}")
            buffer.write("\n")

        # End of Section - Form_feed: https://www.ascii-code.com/12
        buffer.write(f"{COMPASS_SECTION_SEPARATOR}")
        buffer.seek(0)
        return buffer

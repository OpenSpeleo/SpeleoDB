from __future__ import annotations

import io
from datetime import datetime
from itertools import pairwise
from typing import TYPE_CHECKING
from typing import Annotated
from typing import Literal

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


class CompassShot(BaseModel):
    from_: Annotated[
        str,
        Field(
            min_length=1,
            max_length=32,
            serialization_alias="from",
        ),
    ]
    to: Annotated[str, Field(min_length=1, max_length=32)]

    azimuth: Annotated[float, Field(..., ge=0, lt=360)]
    delta_depth: Annotated[float, Field(ge=-1000, le=1000)]
    length: Annotated[float, Field(ge=0, le=1000)]

    # LRUD
    left: Annotated[float, Field(ge=0)] | None = None
    right: Annotated[float, Field(ge=0)] | None = None
    up: Annotated[float, Field(ge=0)] | None = None
    down: Annotated[float, Field(ge=0)] | None = None

    # Optional
    flags: Annotated[str, Field(max_length=5)] | None = None
    comment: Annotated[str, Field(max_length=256)] | None = None

    # Convert stringified numbers to floats
    @field_validator(
        "azimuth",
        "delta_depth",
        "length",
        "left",
        "right",
        "up",
        "down",
        mode="before",
    )
    @classmethod
    def parse_numeric_str(cls, v: Any) -> float | None:
        if v in ("", None):
            return None

        try:
            return round(float(v), 2)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Expected numeric or empty value, got {v!r}") from e

    @field_validator("flags", mode="before")
    @classmethod
    def normalize_flags(cls, v: str | None) -> str | None:
        if v is None:
            return v

        if not isinstance(v, str):
            raise TypeError("flags must be a string")

        # Remove Start & Stop Tokens
        v = v.lstrip(ShotFlag.__start_token__)
        v = v.rstrip(ShotFlag.__end_token__)

        # Verify flag validity
        allowed_flags = {flag.value for flag in ShotFlag}
        chars = list(v.strip())

        if not all(c in allowed_flags for c in chars):
            invalid = [c for c in chars if c not in allowed_flags]
            raise ValueError(f"Invalid flag characters: {invalid}")

        # Sort alphabetically & remove duplicates for consistency
        return "".join(sorted(set(chars)))


class DeclinationObj(BaseModel):
    survey_date: PastDate
    latitude: Annotated[float, Field(ge=-90.0, le=90.0)]
    longitude: Annotated[float, Field(ge=-180.0, le=180.0)]

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
    cave_name: Annotated[str, Field(min_length=1, max_length=64)]
    survey_name: Annotated[str, Field(min_length=1, max_length=64)]
    survey_date: PastDate

    survey_team: Annotated[list[str], Field(min_length=0)]

    unit: Literal["feet", "meters"]
    comment: Annotated[str, Field(max_length=512)] | None
    declination: Annotated[float, Field(ge=-90.0, le=90.0)]

    shots: Annotated[list[CompassShot], Field(min_length=1)]

    @field_validator("survey_team")
    @classmethod
    def strip_team_names(cls, v: list[str]) -> list[str]:
        return [name.strip() for name in v if name.strip()]

    @model_validator(mode="before")
    @classmethod
    def validate_model(cls, data: dict[str, Any]) -> dict[str, Any]:
        shots: list[dict[str, Any]] | None = data.pop("shots", None)

        # ========================= Shot Validation ========================= #

        if shots is None or not len(shots):
            raise ValueError("No shot data received ...")

        if len(shots) < 2:  # noqa: PLR2004
            raise ValueError(
                "A minimum of 2 entries must be received. Only 1 received ..."
            )

        # The last shot should only contain: `station` and `depth` - no length/azimuth/LRUD/flags/comment  # noqa: E501
        last_shot = shots[-1]
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
            if val := last_shot.get(key, None):
                raise ValueError(
                    f"The last shot can not contain any value for `{key}`, "
                    f"received: {val}."
                )

        # ========================= Shot Processing ========================= #

        output_shots: list[dict[str, Any]] = []
        for station_start, station_end in pairwise(shots):
            delta_depth = float(station_end["depth"]) - float(station_start["depth"])

            try:
                shot_length = float(station_start["length"])
            except TypeError as e:
                raise ValueError(
                    f"Shot `{station_start['station']}` must have length defined."
                ) from e

            if abs(delta_depth) > shot_length:
                raise ValueError(
                    f"Shot `{station_start['station']}` has an invalid length."
                    f"\n\t- Length: {shot_length}"
                    f"\n\t- Delta Depth: {delta_depth}"
                )

            shot_data = station_start.copy()
            shot_data.update(
                {
                    "from_": shot_data.pop("station"),
                    "to": station_end["station"],
                    "delta_depth": delta_depth,
                }
            )

            output_shots.append(shot_data)

        data["shots"] = output_shots

        data["declination"] = DeclinationObj(
            survey_date=data["survey_date"],
            longitude=data.pop("longitude"),
            latitude=data.pop("latitude"),
        ).declination

        return data

    @property
    def survey_format(self) -> str:
        # File Format (Line 5). For backward compatibility, this item is optional.
        # This field specifies the format of the original survey notebook. Since Compass
        # converts the file to fixed format, this information is used by programs like
        # the editor to display and edit the data in original form. The field begins
        # with the string: "FORMAT: " followed by 11, 12 or 13 upper case alphabetic
        # characters. Each character specifies a particular part of the format.

        # Compatibility Issues. Over time, the Compass Format string has changed to
        # accommodate more format information. For backward compatibility, Compass can
        # read all previous versions of the format. Here is detailed information about
        # different versions of the Format strings:

        # (U = Units, D = Dimension Order, S = Shot Order, B = Backsight Info, L = LRUD association)  # noqa: E501

        # 11-Character Format. The earliest version of the string had 11 characters
        # like this: UUUUDDDDSSS

        # 12-Character Format. The next version had 12 characters, adding Backsight
        # information: UUUUDDDDSSSB

        # 13-Character Format. The next version had 13 characters, adding information
        # about the LRUD associations: UUUUDDDDSSSBL

        # 15-Character Format. Finally, the current version has 15 characters, adding
        # backsights to order information: UUUUDDDDSSSSSBL

        # ---------------------------------------------------------------------------- #
        #
        # Here is a list of the format items:

        # XIV.	Backsight: B=Redundant, N or empty=No Redundant Backsights.
        # XV.	LRUD Association: F=From Station, T=To Station

        cformat = ""

        # I.	Bearing Units: D = Degrees, Q = quads, R = Grads
        cformat += "D"

        # II.	Length Units: D = Decimal Feet, I = Feet and Inches M = Meters
        cformat += "D" if self.unit == "feet" else "M"

        # III.	Passage Units: Same as length
        cformat += "D" if self.unit == "feet" else "M"

        # IV.	Inclination Units:
        #         - D = Degrees
        #         - G = Percent Grade
        #         - M = Degrees and Minutes
        #         - R = Grads
        #         - W = Depth Gauge
        cformat += "W"

        # V.	Passage Dimension Order: U = Up, D = Down, R = Right L = Left
        cformat += "L"
        # VI.	Passage Dimension Order: U = Up, D = Down, R = Right L = Left
        cformat += "R"
        # VII.	Passage Dimension Order: U = Up, D = Down, R = Right L = Left
        cformat += "U"
        # VIII.	Passage Dimension Order: U = Up, D = Down, R = Right L = Left
        cformat += "D"

        # IX.	Shot Item Order:
        #         - L = Length
        #         - A = Azimuth
        #         - D = Inclination
        #         - a = Back Azimuth
        #         - d = Back Inclination
        cformat += "L"

        # X.	Shot Item Order:
        #         - L = Length
        #         - A = Azimuth
        #         - D = Inclination
        #         - a = Back Azimuth
        #         - d = Back Inclination
        cformat += "A"

        # XI.	Shot Item Order:
        #         - L = Length
        #         - A = Azimuth
        #         - D = Inclination
        #         - a = Back Azimuth
        #         - d = Back Inclination
        cformat += "D"

        # XII.	Shot Item Order:
        #         - L = Length
        #         - A = Azimuth
        #         - D = Inclination
        #         - a = Back Azimuth
        #         - d = Back Inclination
        #         - B = Redundant
        #         - N or empty = No Redundant Backsights
        cformat += "N"

        # XIII.	Shot Item Order:
        #         - L = Length
        #         - A = Azimuth
        #         - D = Inclination
        #         - a = Back Azimuth
        #         - d = Back Inclination
        #         - B = Redundant
        #         - N or empty = No Redundant Backsights
        cformat += "N"

        return cformat

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
        buffer.write(f"SURVEY NAME: {self.survey_name.replace(' ', '_')}\n")
        buffer.write(f"SURVEY DATE: {self.survey_date.strftime('%m %-d %Y')}\n")
        buffer.write(f"COMMENT: {self.comment}\n")
        buffer.write(f"SURVEY TEAM:\n{', '.join(self.survey_team)}\n")
        buffer.write(f"DECLINATION: {self.declination:>7.02f}  ")
        buffer.write(f"FORMAT: {self.survey_format}  ")
        buffer.write(
            f"CORRECTIONS:  {' '.join(f'{nbr:.02f}' for nbr in self.correction)}  "
        )
        buffer.write(
            f"CORRECTIONS2:  {' '.join(f'{nbr:.02f}' for nbr in self.correction2)}\n\n"
        )

        # Shots - Header
        buffer.write("        FROM           TO   LENGTH  BEARING   ΔDEPTH")
        buffer.write("     LEFT    RIGHT       UP     DOWN  FLAGS  COMMENTS\n\n")

        # Shots - Data
        for shot in self.shots:
            buffer.write(f"{shot.from_: >12} ")
            buffer.write(f"{shot.to: >12} ")
            buffer.write(f"{shot.length:8.2f} ")
            buffer.write(f"{shot.azimuth:8.2f} ")
            # In Compass - Delta Depth is the negative.
            # - x < 0: Means going down/deeper
            # - x > 0: Means going up/shallower
            buffer.write(f"{-shot.delta_depth:8.2f} ")
            buffer.write(f"{shot.left if shot.left is not None else -9999:8.2f} ")
            buffer.write(f"{shot.right if shot.right is not None else -9999:8.2f} ")
            buffer.write(f"{shot.up if shot.up is not None else -9999:8.2f} ")
            buffer.write(f"{shot.down if shot.down is not None else -9999:8.2f} ")
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

"""Wire inputs for spreadsheet tools, before their internal shot conversion."""

from __future__ import annotations

from typing import Any


def numeric_cell(*, blank: bool = False) -> dict[str, Any]:
    """Spreadsheet cells arrive as numbers or textual numbers."""
    textual: dict[str, Any] = {
        "type": "string",
        "pattern": r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$",
    }
    if blank:
        textual["nullable"] = True
        textual["pattern"] = r"^(?:[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)?$"
    return {"oneOf": [{"type": "number"}, textual]}


def spreadsheet_input(*, compass: bool) -> dict[str, Any]:
    """The final row is a station/depth terminator, not a measured shot."""
    cells = {
        name: numeric_cell(blank=True)
        for name in ("depth", "length", "azimuth", "left", "right", "up", "down")
    }
    shot_required = ["depth"]
    if compass:
        cells["depth"] = numeric_cell()
        cells.update(
            {
                "station": {"type": "string", "minLength": 1, "maxLength": 32},
                "flags": {"type": "string", "nullable": True},
                "comment": {"type": "string", "nullable": True, "maxLength": 256},
            }
        )
        shot_required.append("station")
    properties: dict[str, Any] = {
        "shots": {
            "type": "array",
            "items": {"type": "object", "properties": cells, "required": shot_required},
            "description": (
                "Rows in survey order. Every measured row supplies length and azimuth; "
                "The final row supplies station/depth and empty measurement cells. "
                "LRUD cells accept numeric values or empty/null cells."
            ),
        },
        "survey_date": {"type": "string", "format": "date"},
        "unit": {"type": "string", "enum": ["feet", "meters"]},
    }
    required = ["shots", "survey_date", "unit"]
    if compass:
        properties["shots"]["minItems"] = 2
        properties.update(
            {
                "cave_name": {"type": "string", "minLength": 1, "maxLength": 64},
                "survey_name": {"type": "string", "minLength": 1, "maxLength": 64},
                "survey_team": {"type": "array", "items": {"type": "string"}},
                "comment": {"type": "string", "nullable": True, "maxLength": 512},
                "latitude": numeric_cell(),
                "longitude": numeric_cell(),
            }
        )
        required.extend(
            [
                "cave_name",
                "survey_name",
                "survey_team",
                "comment",
                "latitude",
                "longitude",
            ]
        )
    else:
        properties["unit"] = {
            "type": "string",
            "description": (
                "feet converts to meters; other values are interpreted as meters."
            ),
        }
        properties["direction"] = {
            "type": "string",
            "description": (
                "in selects inward direction; other values select outward direction."
            ),
        }
        required.append("direction")
    return {"type": "object", "properties": properties, "required": required}

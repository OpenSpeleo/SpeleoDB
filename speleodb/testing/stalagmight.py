"""Small native SQLite sources shared by upload and map-generation tests."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from uuid import UUID

MAX_SOURCE_BYTES = 100_000
NATIVE_SHOT_ID = UUID(int=2, version=4)

SCHEMA = """
CREATE TABLE project(id INTEGER, name TEXT, location TEXT, created_at TEXT,
 modified_at TEXT, schema_version INTEGER);
CREATE TABLE sections(id INTEGER, name TEXT, surveyor TEXT, date TEXT,
 color TEXT, direction TEXT, quality REAL, created_at TEXT,
 gauge_shot_uuid TEXT, gauge_neighbour_uuid TEXT, reverse_parity INTEGER,
 azimuth_north TEXT, azimuth_correction REAL, azimuth_source TEXT,
 azimuth_epoch_year INTEGER);
CREATE TABLE shots(id INTEGER, section_id INTEGER, sequence_order INTEGER,
 azimuth_in REAL, azimuth_out REAL, length REAL, depth_in REAL, depth_out REAL,
 pitch_in REAL, pitch_out REAL, left_distance REAL, right_distance REAL,
 up_distance REAL, down_distance REAL, comment TEXT, kind INTEGER,
 marker_index INTEGER, temperature REAL, uuid TEXT);
CREATE TABLE zero_datums(id INTEGER, section_id INTEGER, station_index INTEGER,
 latitude REAL, longitude REAL, depth_reference REAL);
CREATE TABLE station_merges(id INTEGER, station_a_section INTEGER,
 station_a_index INTEGER, station_b_section INTEGER, station_b_index INTEGER,
 merged_at TEXT);
"""


def stalagmight_bytes(
    *,
    schema_version: int = 18,
    anchored: bool = True,
    length: float = 10.0,
) -> bytes:
    """Make two merged sections, a hidden jump, and a corrected/depth-offset leg.

    The ordinary leg changes depth by six metres. Setting its length below six
    creates a valid native survey whose impossible geometry the exporter rejects.
    """
    with closing(sqlite3.connect(":memory:")) as database, database:
        database.executescript(SCHEMA)
        database.execute("PRAGMA user_version=18")
        database.execute(
            "INSERT INTO project VALUES(1, 'Native survey', NULL, ?, ?, ?)",
            ("2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z", schema_version),
        )
        database.executemany(
            "INSERT INTO sections VALUES(?, ?, NULL, '2026-01-01', ?, 'in', "
            "1, '2026-01-01T00:00:00Z', NULL, NULL, 0, 'magnetic', 90, "
            "'manual', NULL)",
            [(1, "Entrance", "#abc"), (2, "Branch", "#336699")],
        )
        database.executemany(
            "INSERT INTO shots VALUES(?, ?, ?, 0, 0, ?, ?, ?, NULL, NULL, "
            "NULL, NULL, NULL, NULL, NULL, ?, NULL, NULL, ?)",
            [
                (1, 1, 0, 5.0, 0.0, 0.0, 1, str(UUID(int=1, version=4))),
                (2, 1, 1, length, 50.0, 56.0, 0, str(NATIVE_SHOT_ID)),
                (3, 2, 0, 10.0, 56.0, 56.0, 0, str(UUID(int=3, version=4))),
            ],
        )
        if anchored:
            database.execute("INSERT INTO zero_datums VALUES(1, 1, 0, 0, 0, 0)")
        database.execute(
            "INSERT INTO station_merges VALUES(1, 1, 2, 2, 0, '2026-01-01T00:00:00Z')"
        )
        database.commit()
        payload = database.serialize()
    assert len(payload) <= MAX_SOURCE_BYTES
    return payload

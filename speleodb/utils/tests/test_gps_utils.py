# -*- coding: utf-8 -*-

from __future__ import annotations

import pytest

from speleodb.utils.gps_utils import format_coordinate
from speleodb.utils.gps_utils import maybe_convert_dms_to_decimal


class TestFormatCoordinate:
    """Test cases for format_coordinate function."""

    def test_format_coordinate_with_integer(self) -> None:
        """Test formatting an integer coordinate."""
        result = format_coordinate(45)
        assert result == 45.0  # noqa: PLR2004
        assert isinstance(result, float)

    def test_format_coordinate_with_float(self) -> None:
        """Test formatting a float coordinate."""
        result = format_coordinate(45.123456789)
        assert result == 45.1234568  # Rounded to 7 decimal places  # noqa: PLR2004
        assert isinstance(result, float)

    def test_format_coordinate_with_string_number(self) -> None:
        """Test formatting a string representation of a number."""
        result = format_coordinate("45.123456789")
        assert result == 45.1234568  # noqa: PLR2004
        assert isinstance(result, float)

    def test_format_coordinate_rounds_to_seven_decimals(self) -> None:
        """Test that coordinate is rounded to exactly 7 decimal places."""
        # Test with more than 7 decimal places
        result = format_coordinate(45.12345678901234)
        assert result == 45.1234568  # noqa: PLR2004

        # Test with exactly 7 decimal places
        result = format_coordinate(45.1234567)
        assert result == 45.1234567  # noqa: PLR2004

        # Test with fewer than 7 decimal places
        result = format_coordinate(45.123)
        assert result == 45.123  # noqa: PLR2004

    def test_format_coordinate_with_zero(self) -> None:
        """Test formatting zero."""
        result = format_coordinate(0)
        assert result == 0.0

    def test_format_coordinate_with_negative(self) -> None:
        """Test formatting negative coordinate."""
        result = format_coordinate(-45.123456789)
        assert result == -45.1234568  # noqa: PLR2004

    def test_format_coordinate_raises_value_error_for_invalid_string(
        self,
    ) -> None:
        """Test that invalid string raises ValueError."""
        with pytest.raises(ValueError, match="could not convert string to float"):
            format_coordinate("invalid")

    def test_format_coordinate_with_none_raises_type_error(self) -> None:
        """Test that None raises TypeError."""
        with pytest.raises(TypeError):
            format_coordinate(None)


class TestMaybeConvertDmsToDecimal:
    """Test cases for maybe_convert_dms_to_decimal function."""

    def test_convert_dms_north(self) -> None:
        """Test converting DMS format with N (North) direction."""
        result = maybe_convert_dms_to_decimal("30°15'03\"N")
        assert isinstance(result, float)
        # 30 + 15/60 + 3/3600 = 30.2508333...
        assert abs(result - 30.2508333) < 1e-4  # noqa: PLR2004

    def test_convert_dms_south(self) -> None:
        """Test converting DMS format with S (South) direction."""
        result = maybe_convert_dms_to_decimal("30°15'03\"S")
        assert isinstance(result, float)
        # Should be negative for South
        assert abs(result - (-30.2508333)) < 1e-4  # noqa: PLR2004

    def test_convert_dms_east(self) -> None:
        """Test converting DMS format with E (East) direction."""
        result = maybe_convert_dms_to_decimal("45°30'15\"E")
        assert isinstance(result, float)
        # 45 + 30/60 + 15/3600 = 45.5041667...
        assert abs(result - 45.5041667) < 1e-4  # noqa: PLR2004

    def test_convert_dms_west(self) -> None:
        """Test converting DMS format with W (West) direction."""
        result = maybe_convert_dms_to_decimal("45°30'15\"W")
        assert isinstance(result, float)
        # Should be negative for West
        assert abs(result - (-45.5041667)) < 1e-4  # noqa: PLR2004

    def test_convert_dms_with_spaces(self) -> None:
        """Test converting DMS format with spaces between components."""
        result = maybe_convert_dms_to_decimal("30° 15' 03\" N")
        assert isinstance(result, float)
        assert abs(result - 30.2508333) < 1e-4  # noqa: PLR2004

    def test_convert_dms_with_decimal_seconds(self) -> None:
        """Test converting DMS format with decimal seconds."""
        result = maybe_convert_dms_to_decimal("30°15'03.5\"N")
        assert isinstance(result, float)
        # 30 + 15/60 + 3.5/3600 = 30.2509722...
        assert abs(result - 30.2509722) < 1e-4  # noqa: PLR2004

    def test_convert_dms_case_insensitive(self) -> None:
        """Test that direction letters are case-insensitive."""
        result_lower = maybe_convert_dms_to_decimal("30°15'03\"n")
        result_upper = maybe_convert_dms_to_decimal("30°15'03\"N")
        assert result_lower == result_upper

        result_lower_s = maybe_convert_dms_to_decimal("30°15'03\"s")
        result_upper_s = maybe_convert_dms_to_decimal("30°15'03\"S")
        assert result_lower_s == result_upper_s

    def test_convert_dms_with_leading_trailing_whitespace(self) -> None:
        """Test that leading and trailing whitespace is handled."""
        result = maybe_convert_dms_to_decimal("  30°15'03\"N  ")
        assert isinstance(result, float)
        assert abs(result - 30.2508333) < 1e-4  # noqa: PLR2004

    def test_convert_dms_without_quote_after_seconds(self) -> None:
        """Test DMS format without quote after seconds."""
        result = maybe_convert_dms_to_decimal("30°15'03N")
        assert isinstance(result, float)
        assert abs(result - 30.2508333) < 1e-4  # noqa: PLR2004

    def test_convert_dms_returns_original_string_if_no_match(self) -> None:
        """Test that non-DMS strings are returned unchanged."""
        # Invalid format - no direction
        result = maybe_convert_dms_to_decimal("30°15'03\"")
        assert result == "30°15'03\""
        assert isinstance(result, str)

        # Invalid format - no degrees symbol
        result = maybe_convert_dms_to_decimal("30 15'03\"N")
        assert result == "30 15'03\"N"
        assert isinstance(result, str)

        # Invalid format - plain number
        result = maybe_convert_dms_to_decimal("45.123")
        assert result == "45.123"
        assert isinstance(result, str)

        # Invalid format - random string
        result = maybe_convert_dms_to_decimal("not a coordinate")
        assert result == "not a coordinate"
        assert isinstance(result, str)

    def test_convert_dms_edge_case_zero_minutes_seconds(self) -> None:
        """Test DMS conversion with zero minutes and seconds."""
        result = maybe_convert_dms_to_decimal("45°0'0\"N")
        assert result == 45.0  # noqa: PLR2004

    def test_convert_dms_edge_case_large_degrees(self) -> None:
        """Test DMS conversion with large degree values."""
        result = maybe_convert_dms_to_decimal("180°0'0\"E")
        assert result == 180.0  # noqa: PLR2004

        result = maybe_convert_dms_to_decimal("180°0'0\"W")
        assert result == -180.0  # noqa: PLR2004

    def test_convert_dms_precise_calculation(self) -> None:
        """Test precise DMS to decimal conversion."""
        # Known value: 37°46'26.2992"N = 37.773972
        result = maybe_convert_dms_to_decimal("37°46'26.2992\"N")
        assert isinstance(result, float)
        expected = 37.773972
        assert abs(result - expected) < 1e-4  # noqa: PLR2004

        # Known value: 122°25'52.6692"W = -122.431297
        result = maybe_convert_dms_to_decimal("122°25'52.6692\"W")
        assert isinstance(result, float)

        expected = -122.431297
        assert abs(result - expected) < 1e-4  # noqa: PLR2004

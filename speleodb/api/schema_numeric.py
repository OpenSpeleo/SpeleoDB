"""Shared decimal grammar for API inputs normalized with Python's float()."""

FLOAT_DIGITS_PATTERN = r"\d(?:_?\d)*"
FLOAT_MANTISSA_PATTERN = (
    rf"(?:{FLOAT_DIGITS_PATTERN}(?:\.(?:{FLOAT_DIGITS_PATTERN})?)?"
    rf"|\.{FLOAT_DIGITS_PATTERN})"
)
FLOAT_EXPONENT_PATTERN = rf"(?:[eE][+-]?{FLOAT_DIGITS_PATTERN})?"

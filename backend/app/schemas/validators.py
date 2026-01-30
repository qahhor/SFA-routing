"""
Shared Pydantic validators for common data types.
"""

from decimal import Decimal
from typing import Annotated, Any

from pydantic import BeforeValidator, Field


def validate_latitude(v: Any) -> Decimal:
    """
    Validate latitude value.

    Latitude must be between -90 and 90 degrees.
    """
    if v is None:
        raise ValueError("Latitude is required")

    try:
        lat = Decimal(str(v))
    except Exception:
        raise ValueError(f"Invalid latitude value: {v}")

    if lat < Decimal("-90") or lat > Decimal("90"):
        raise ValueError(f"Latitude must be between -90 and 90, got {lat}")

    return lat


def validate_longitude(v: Any) -> Decimal:
    """
    Validate longitude value.

    Longitude must be between -180 and 180 degrees.
    """
    if v is None:
        raise ValueError("Longitude is required")

    try:
        lon = Decimal(str(v))
    except Exception:
        raise ValueError(f"Invalid longitude value: {v}")

    if lon < Decimal("-180") or lon > Decimal("180"):
        raise ValueError(f"Longitude must be between -180 and 180, got {lon}")

    return lon


def validate_latitude_optional(v: Any) -> Decimal | None:
    """Validate optional latitude value."""
    if v is None:
        return None
    return validate_latitude(v)


def validate_longitude_optional(v: Any) -> Decimal | None:
    """Validate optional longitude value."""
    if v is None:
        return None
    return validate_longitude(v)


def validate_positive_decimal(v: Any) -> Decimal:
    """Validate that decimal is positive."""
    if v is None:
        raise ValueError("Value is required")

    try:
        val = Decimal(str(v))
    except Exception:
        raise ValueError(f"Invalid decimal value: {v}")

    if val < Decimal("0"):
        raise ValueError(f"Value must be positive, got {val}")

    return val


def validate_phone(v: Any) -> str | None:
    """
    Validate phone number format.

    Accepts formats like:
    - +998901234567
    - +7 (999) 123-45-67
    - 998901234567
    """
    if v is None or v == "":
        return None

    phone = str(v).strip()

    # Remove common formatting characters
    cleaned = "".join(c for c in phone if c.isdigit() or c == "+")

    if len(cleaned) < 9:
        raise ValueError(f"Phone number too short: {phone}")

    if len(cleaned) > 15:
        raise ValueError(f"Phone number too long: {phone}")

    return phone


# Annotated types for use in Pydantic models
Latitude = Annotated[
    Decimal,
    BeforeValidator(validate_latitude),
    Field(ge=-90, le=90, description="Latitude in degrees (-90 to 90)"),
]

Longitude = Annotated[
    Decimal,
    BeforeValidator(validate_longitude),
    Field(ge=-180, le=180, description="Longitude in degrees (-180 to 180)"),
]

LatitudeOptional = Annotated[
    Decimal | None,
    BeforeValidator(validate_latitude_optional),
    Field(default=None, ge=-90, le=90, description="Optional latitude in degrees"),
]

LongitudeOptional = Annotated[
    Decimal | None,
    BeforeValidator(validate_longitude_optional),
    Field(default=None, ge=-180, le=180, description="Optional longitude in degrees"),
]

PositiveDecimal = Annotated[
    Decimal,
    BeforeValidator(validate_positive_decimal),
    Field(ge=0, description="Positive decimal value"),
]

PhoneNumber = Annotated[
    str | None,
    BeforeValidator(validate_phone),
    Field(default=None, max_length=20, description="Phone number"),
]


# Coordinate bounds for Central Asia region
class CoordinateBounds:
    """Geographic bounds for validation."""

    # Uzbekistan approximate bounds
    UZ_LAT_MIN = Decimal("37.0")
    UZ_LAT_MAX = Decimal("45.6")
    UZ_LON_MIN = Decimal("56.0")
    UZ_LON_MAX = Decimal("73.2")

    # Kazakhstan approximate bounds
    KZ_LAT_MIN = Decimal("40.5")
    KZ_LAT_MAX = Decimal("55.5")
    KZ_LON_MIN = Decimal("46.5")
    KZ_LON_MAX = Decimal("87.4")

    # Combined Central Asia bounds
    CA_LAT_MIN = Decimal("37.0")
    CA_LAT_MAX = Decimal("55.5")
    CA_LON_MIN = Decimal("46.5")
    CA_LON_MAX = Decimal("87.4")

    @classmethod
    def is_in_uzbekistan(cls, lat: Decimal, lon: Decimal) -> bool:
        """Check if coordinates are within Uzbekistan bounds."""
        return cls.UZ_LAT_MIN <= lat <= cls.UZ_LAT_MAX and cls.UZ_LON_MIN <= lon <= cls.UZ_LON_MAX

    @classmethod
    def is_in_kazakhstan(cls, lat: Decimal, lon: Decimal) -> bool:
        """Check if coordinates are within Kazakhstan bounds."""
        return cls.KZ_LAT_MIN <= lat <= cls.KZ_LAT_MAX and cls.KZ_LON_MIN <= lon <= cls.KZ_LON_MAX

    @classmethod
    def is_in_central_asia(cls, lat: Decimal, lon: Decimal) -> bool:
        """Check if coordinates are within Central Asia bounds."""
        return cls.CA_LAT_MIN <= lat <= cls.CA_LAT_MAX and cls.CA_LON_MIN <= lon <= cls.CA_LON_MAX


def validate_central_asia_coordinates(lat: Decimal, lon: Decimal) -> tuple[Decimal, Decimal]:
    """
    Validate that coordinates are within Central Asia region.

    Raises ValueError if coordinates are outside the region.
    """
    if not CoordinateBounds.is_in_central_asia(lat, lon):
        raise ValueError(
            f"Coordinates ({lat}, {lon}) are outside Central Asia region. "
            f"Expected lat: {CoordinateBounds.CA_LAT_MIN}-{CoordinateBounds.CA_LAT_MAX}, "
            f"lon: {CoordinateBounds.CA_LON_MIN}-{CoordinateBounds.CA_LON_MAX}"
        )
    return (lat, lon)

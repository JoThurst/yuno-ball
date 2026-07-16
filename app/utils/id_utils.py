"""Canonical NBA identifier helpers used at ingestion boundaries."""

from __future__ import annotations

from typing import Any


class InvalidNBAIdentifier(ValueError):
    """Raised when a provider value cannot be represented as an NBA ID."""


def normalize_nba_game_id(value: Any) -> str:
    """Return the canonical ten-digit NBA game ID.

    Provider clients sometimes deserialize IDs as integers and drop leading
    zeroes. New durable writes normalize them at the boundary; non-numeric or
    overlong values fail closed instead of creating a second identity.
    """

    if value is None or isinstance(value, bool):
        raise InvalidNBAIdentifier("NBA game_id is required")
    text = str(value).strip()
    if not text or not text.isdigit():
        raise InvalidNBAIdentifier(f"Invalid NBA game_id: {value!r}")
    if len(text) > 10:
        raise InvalidNBAIdentifier(f"NBA game_id is longer than ten digits: {value!r}")
    return text.zfill(10)

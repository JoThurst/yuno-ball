"""Deprecated compatibility entry point for the legacy player_z_scores writer.

The retained table has no season, cutoff, source, or calculation-version key,
so writing it would destroy analytical context. Phase 2 player heat snapshots
are the supported normalized player-comparison contract.
"""

from __future__ import annotations


class DeprecatedZScorePipeline(RuntimeError):
    """Raised when code attempts to run the unsafe legacy writer."""


def populate_z_scores(*args, **kwargs) -> int:
    """Fail closed instead of overwriting the unversioned legacy table."""

    raise DeprecatedZScorePipeline(
        "player_z_scores is read-only legacy data; publish versioned "
        "player_heat_index_snapshots through the daily snapshot pipeline"
    )


if __name__ == "__main__":
    populate_z_scores()

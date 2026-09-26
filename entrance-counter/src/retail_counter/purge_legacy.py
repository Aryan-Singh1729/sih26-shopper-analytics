"""Targeted removal of inspected events from retired detector namespaces."""

from __future__ import annotations

import sqlite3


def purge_legacy_events(connection: sqlite3.Connection, legacy_camera_ids: set[str]) -> int:
    if any(camera_id.endswith(":presence-person-v1") for camera_id in legacy_camera_ids):
        raise ValueError("refusing to purge a new-model camera ID")
    if not legacy_camera_ids:
        return 0
    ids = sorted(legacy_camera_ids)
    placeholders = ",".join("?" for _ in ids)
    cursor = connection.execute(
        f"DELETE FROM crossing_events WHERE camera_id IN ({placeholders})",
        ids,
    )
    connection.commit()
    return cursor.rowcount


def purge_inspected_legacy_events(
    connection: sqlite3.Connection, expected_legacy_counts: dict[str, int], expected_new_count: int
) -> int:
    """Purge only when the entire event inventory matches the preflight audit."""
    if not expected_legacy_counts or any(
        camera_id.endswith(":presence-person-v1") for camera_id in expected_legacy_counts
    ):
        raise ValueError("invalid legacy ID set")
    actual = dict(connection.execute(
        "SELECT camera_id, COUNT(*) FROM crossing_events GROUP BY camera_id"
    ).fetchall())
    expected = dict(expected_legacy_counts)
    expected["entrance-fixed-2:presence-person-v1"] = expected_new_count
    if actual != expected:
        raise ValueError(f"event inventory changed: {actual!r}")
    deleted = purge_legacy_events(connection, set(expected_legacy_counts))
    remaining = dict(connection.execute(
        "SELECT camera_id, COUNT(*) FROM crossing_events GROUP BY camera_id"
    ).fetchall())
    if remaining != {"entrance-fixed-2:presence-person-v1": expected_new_count}:
        raise RuntimeError(f"unexpected post-purge inventory: {remaining!r}")
    return deleted

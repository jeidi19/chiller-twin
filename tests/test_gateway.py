"""Gateway plumbing that does not depend on the MQTT payload format."""

from datetime import UTC, datetime, timedelta

from gateway.__main__ import SnapshotAssembler

T0 = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)
T1 = T0 + timedelta(seconds=1)


def test_snapshot_is_emitted_only_when_complete():
    a = SnapshotAssembler(fields=("x", "y"))
    assert a.add("x", 1.0, T0) is None
    assert a.add("y", 2.0, T0) == (T0, {"x": 1.0, "y": 2.0})


def test_interleaved_samples_are_kept_apart():
    a = SnapshotAssembler(fields=("x", "y"))
    a.add("x", 1.0, T0)
    a.add("x", 10.0, T1)
    assert a.add("y", 2.0, T0) == (T0, {"x": 1.0, "y": 2.0})
    assert a.add("y", 20.0, T1) == (T1, {"x": 10.0, "y": 20.0})


def test_incomplete_older_snapshot_is_dropped_and_late_values_ignored():
    a = SnapshotAssembler(fields=("x", "y"))
    a.add("x", 1.0, T0)  # its "y" is lost
    a.add("x", 10.0, T1)
    assert a.add("y", 20.0, T1) == (T1, {"x": 10.0, "y": 20.0})
    assert a.add("y", 2.0, T0) is None

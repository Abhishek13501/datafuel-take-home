from sweep import normalize_timestamp


def test_normalize_timestamp_utc():
    result = normalize_timestamp("2026-09-28T04:37:00Z")
    assert result == "2026-09-28T04:37:00Z"


def test_normalize_timestamp_timezone():
    result = normalize_timestamp("2026-09-28T10:07:00+05:30")
    assert result == "2026-09-28T04:37:00Z"
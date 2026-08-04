# =====================================================================
# tests/test_quality.py
#
# Tests for pipeline/quality.py -- specifically confirms each check
# correctly FAILS on bad data, not just that it passes on good data.
#
# A check that always passes would be worthless. These tests
# deliberately break one field at a time and confirm the relevant
# check catches it.
# =====================================================================

import pandas as pd
from pipeline.quality import check_consistency, check_ranges, check_nulls


def make_valid_row():
    """A single row that satisfies every quality rule -- the baseline
    'known good' row each test starts from and then deliberately
    corrupts one field at a time."""
    return pd.DataFrame([{
        "team_name": "Test FC", "league_name": "Premier League",
        "mp": 38, "w": 20, "d": 10, "l": 8,
        "gf": 60, "ga": 40, "gd": 20, "pts": 70, "pts_per_mp": 1.84
    }])


def test_consistency_check_passes_on_valid_row():
    """Sanity check: the consistency rule (w+d+l=mp) should pass on
    data that's actually internally consistent."""
    df = make_valid_row()
    result = check_consistency(df)
    assert result.passed


def test_consistency_check_fails_on_bad_row():
    """The real test: breaking mp so w+d+l no longer equals it should
    cause the check to correctly report a failure."""
    df = make_valid_row()
    df.loc[0, "mp"] = 10
    result = check_consistency(df)
    assert not result.passed


def test_range_check_fails_on_negative_wins():
    """Confirms the range check catches an impossible value --
    a team can't have negative wins."""
    df = make_valid_row()
    df.loc[0, "w"] = -1
    result = check_ranges(df)
    assert not result.passed


def test_null_check_fails_on_missing_team_name():
    """Confirms the null check catches a missing required field."""
    df = make_valid_row()
    df.loc[0, "team_name"] = None
    result = check_nulls(df)
    assert not result.passed
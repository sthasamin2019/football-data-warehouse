
import pandas as pd
from pipeline.quality import check_consistency, check_ranges, check_nulls

def make_valid_row():
    return pd.DataFrame([{
        "team_name": "Test FC", "league_name": "Premier League",
        "mp": 38, "w": 20, "d": 10, "l": 8,
        "gf": 60, "ga": 40, "gd": 20, "pts": 70, "pts_per_mp": 1.84
    }])

def test_consistency_check_passes_on_valid_row():
    df = make_valid_row()
    result = check_consistency(df)
    assert result.passed

def test_consistency_check_fails_on_bad_row():
    df = make_valid_row()
    df.loc[0, "mp"] = 10
    result = check_consistency(df)
    assert not result.passed

def test_range_check_fails_on_negative_wins():
    df = make_valid_row()
    df.loc[0, "w"] = -1
    result = check_ranges(df)
    assert not result.passed

def test_null_check_fails_on_missing_team_name():
    df = make_valid_row()
    df.loc[0, "team_name"] = None
    result = check_nulls(df)
    assert not result.passed

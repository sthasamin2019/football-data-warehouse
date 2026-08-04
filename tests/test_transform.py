# =====================================================================
# tests/test_transform.py
#
# Tests for pipeline/transform.py -- confirms the regex-based scorer
# field parsing works correctly, and that transform() returns the
# right shape of data (all expected tables, real + synthetic combined
# correctly).
# =====================================================================

import pandas as pd
from pipeline.extract import extract
from pipeline.transform import transform, split_scorer_field


def test_split_scorer_field_simple():
    """Confirms the regex correctly splits a clean 'Name - N' string
    into a separate name and goal count."""
    name, goals = split_scorer_field("Robert Lewandowski - 17")
    assert name == "Robert Lewandowski"
    assert goals == 17


def test_transform_returns_all_tables():
    """Confirms transform() returns exactly the 5 expected keys --
    catches accidental key renames or missing tables in the return
    dict before load.py tries to use them."""
    raw = extract()
    result = transform(raw)
    expected_keys = {"teams", "team_season_stats", "team_season_stats_real_only", "top_scorers", "goalkeepers"}
    assert set(result.keys()) == expected_keys


def test_transform_league_mapping_complete():
    """Confirms every row in the combined dataset has a team_name --
    a basic sanity check that the transform didn't silently drop or
    corrupt rows."""
    raw = extract()
    result = transform(raw)
    assert result["team_season_stats"]["team_name"].notna().all()


def test_transform_row_counts_include_synthetic():
    """Confirms the combined dataset is genuinely LARGER than the raw
    real data (proving synthetic rows were actually added), while the
    real-only table stays exactly the size of the source CSV."""
    raw = extract()
    result = transform(raw)
    assert len(result["team_season_stats"]) > len(raw)
    assert len(result["team_season_stats_real_only"]) == len(raw)
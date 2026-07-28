
import pandas as pd
from pipeline.extract import extract
from pipeline.transform import transform, split_scorer_field

def test_split_scorer_field_simple():
    name, goals = split_scorer_field("Robert Lewandowski - 17")
    assert name == "Robert Lewandowski"
    assert goals == 17

def test_transform_returns_all_tables():
    raw = extract()
    result = transform(raw)
    expected_keys = {"teams", "team_season_stats", "team_season_stats_real_only", "top_scorers", "goalkeepers"}
    assert set(result.keys()) == expected_keys

def test_transform_league_mapping_complete():
    raw = extract()
    result = transform(raw)
    assert result["team_season_stats"]["team_name"].notna().all()

def test_transform_row_counts_include_synthetic():
    raw = extract()
    result = transform(raw)
    assert len(result["team_season_stats"]) > len(raw)
    assert len(result["team_season_stats_real_only"]) == len(raw)

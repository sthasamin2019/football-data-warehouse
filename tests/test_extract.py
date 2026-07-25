import pandas as pd
from pipeline.extract import extract, EXPECTED_COLUMNS

def test_extract_returns_dataframe():
    df = extract()
    assert isinstance(df, pd.DataFrame)

def test_extract_has_expected_columns():
    df = extract()
    assert set(EXPECTED_COLUMNS).issubset(set(df.columns))

def test_extract_has_rows():
    df = extract()
    assert len(df) > 0
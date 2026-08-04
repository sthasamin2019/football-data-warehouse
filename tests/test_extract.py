# =====================================================================
# tests/test_extract.py
#
# Tests for pipeline/extract.py -- confirms the extract stage returns
# usable, correctly-shaped data before the rest of the pipeline
# depends on it.
# =====================================================================

import pandas as pd
from pipeline.extract import extract, EXPECTED_COLUMNS


def test_extract_returns_dataframe():
    """Confirms extract() returns a pandas DataFrame, not some other
    type -- the whole rest of the pipeline assumes this."""
    df = extract()
    assert isinstance(df, pd.DataFrame)


def test_extract_has_expected_columns():
    """Confirms every column extract.py expects is actually present.
    If the source CSV ever changes and a column is renamed or
    dropped, this test fails clearly instead of the bug surfacing
    silently deep inside transform.py."""
    df = extract()
    assert set(EXPECTED_COLUMNS).issubset(set(df.columns))


def test_extract_has_rows():
    """Confirms extract() didn't silently return an empty dataset --
    e.g. if the CSV path pointed at an empty or corrupted file."""
    df = extract()
    assert len(df) > 0
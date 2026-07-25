import pandas as pd
import logging
import os

logging.basicConfig(
    filename=os.path.join("logs", "quality.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

KNOWN_LEAGUES = {"Premier League", "La Liga", "Serie A", "Ligue 1", "Bundesliga"}


class QualityCheckResult:
    def __init__(self, name, passed, details=""):
        self.name = name
        self.passed = passed
        self.details = details

    def __repr__(self):
        status = "PASS" if self.passed else "FAIL"
        return f"[{status}] {self.name}: {self.details}"


def check_nulls(stats_df: pd.DataFrame) -> QualityCheckResult:
    required_cols = ["team_name", "league_name", "mp", "w", "d", "l", "gf", "ga", "pts"]
    null_counts = stats_df[required_cols].isna().sum()
    bad_cols = null_counts[null_counts > 0]
    passed = bad_cols.empty
    details = "No nulls in required fields" if passed else f"Nulls found: {bad_cols.to_dict()}"
    return QualityCheckResult("null_check", passed, details)


def check_ranges(stats_df: pd.DataFrame) -> QualityCheckResult:
    issues = []
    if (stats_df["mp"] < 0).any() or (stats_df["mp"] > 38).any():
        issues.append("mp out of [0,38] range")
    if (stats_df["pts_per_mp"] > 3).any():
        issues.append("pts_per_mp exceeds 3.0")
    if (stats_df["w"] < 0).any() or (stats_df["d"] < 0).any() or (stats_df["l"] < 0).any():
        issues.append("negative w/d/l found")
    passed = len(issues) == 0
    details = "All values within expected ranges" if passed else "; ".join(issues)
    return QualityCheckResult("range_check", passed, details)


def check_consistency(stats_df: pd.DataFrame) -> QualityCheckResult:
    mp_mismatch = stats_df[stats_df["w"] + stats_df["d"] + stats_df["l"] != stats_df["mp"]]
    gd_mismatch = stats_df[stats_df["gd"] != (stats_df["gf"] - stats_df["ga"])]
    issues = []
    if not mp_mismatch.empty:
        issues.append(f"{len(mp_mismatch)} rows where w+d+l != mp")
    if not gd_mismatch.empty:
        issues.append(f"{len(gd_mismatch)} rows where gd != gf-ga")
    passed = len(issues) == 0
    details = "All rows internally consistent" if passed else "; ".join(issues)
    return QualityCheckResult("consistency_check", passed, details)


def check_uniqueness(stats_df: pd.DataFrame) -> QualityCheckResult:
    dupes = stats_df.duplicated(subset=["team_name", "stats_date"]).sum()
    passed = dupes == 0
    details = "No duplicate team/date rows" if passed else f"{dupes} duplicate rows found"
    return QualityCheckResult("uniqueness_check", passed, details)


def check_league_reference(stats_df: pd.DataFrame) -> QualityCheckResult:
    unknown = set(stats_df["league_name"].unique()) - KNOWN_LEAGUES
    passed = len(unknown) == 0
    details = "All leagues recognized" if passed else f"Unknown leagues: {unknown}"
    return QualityCheckResult("league_reference_check", passed, details)


def run_quality_checks(stats_df: pd.DataFrame) -> list:
    checks = [
        check_nulls(stats_df),
        check_ranges(stats_df),
        check_consistency(stats_df),
        check_uniqueness(stats_df),
        check_league_reference(stats_df),
    ]

    for result in checks:
        if result.passed:
            logging.info(str(result))
        else:
            logging.error(str(result))

    failed = [c for c in checks if not c.passed]
    if failed:
        logging.error(f"{len(failed)} quality check(s) failed out of {len(checks)}")
    else:
        logging.info(f"All {len(checks)} quality checks passed")

    return checks


if __name__ == "__main__":
    from pipeline.extract import extract
    from pipeline.transform import transform

    raw = extract()
    result = transform(raw)
    checks = run_quality_checks(result["team_season_stats"])

    print("\n--- Quality Check Results ---")
    for c in checks:
        print(c)
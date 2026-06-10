from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "data_policy" / "FAST_EXPLORATORY_DATA_POLICY.md"


def test_fast_exploratory_data_policy_exists() -> None:
    assert POLICY.exists()
    text = POLICY.read_text(encoding="utf-8")
    assert "Early historical screening does not require perfect data" in text
    assert "yfinance-compatible adjusted daily price path" in text
    assert "exploratory, non-final" in text
    assert "Basic QA is required" in text
    assert "Raw OHLCV stays in the approved local cache" in text


def test_policy_keeps_strict_lanes_strict() -> None:
    text = POLICY.read_text(encoding="utf-8")
    assert "Individual stocks remain stricter" in text
    assert "Options, futures, forex, intraday" in text
    assert "Paper-forward observation and candidate_exhaustive remain strict lanes" in text
    assert "real-money recommendation" in text


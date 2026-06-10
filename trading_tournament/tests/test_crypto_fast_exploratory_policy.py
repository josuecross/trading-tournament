from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "data_policy" / "FAST_EXPLORATORY_CRYPTO_SPOT_POLICY.md"


def test_crypto_fast_exploratory_policy_exists() -> None:
    assert POLICY.exists()
    text = POLICY.read_text(encoding="utf-8")
    assert "Crypto spot data can be used for Tier 2 exploratory historical screens" in text
    assert "BTC-USD" in text
    assert "ETH-USD" in text
    assert "exploratory, non-final, not paper-forward, and not real-money" in text
    assert "Candidate_exhaustive and paper-forward lanes remain strict" in text
    assert "separate from ETF/fund core evidence" in text


def test_crypto_policy_forbids_high_risk_mechanics() -> None:
    text = POLICY.read_text(encoding="utf-8")
    for phrase in [
        "no leverage",
        "no margin",
        "no shorting",
        "no futures",
        "no perpetual swaps",
        "no options",
        "no exchange execution",
        "no broker integration",
        "no live orders",
        "no real-money recommendation",
    ]:
        assert phrase in text

from __future__ import annotations

from pathlib import Path

import pandas as pd

import run_advisor_consistency_check as consistency


def exact_rolling(strategy: str = "SPY_200d_trend_model") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "lane": "independent_family_challenge",
                "strategy": strategy,
                "family_id": "family_broad_etf_spy200d_v1",
                "horizon": 90,
                "standard_or_stress": "standard",
                "rolling_method": "all_possible",
                "number_of_windows": 10,
                "possible_window_count": 10,
                "final_validation_completed": True,
                "sampled_results_are_final": True,
                "rolling_status": "completed",
                "credibility_tier": "tier3_candidate_validation",
            }
        ]
    )


def completed_challenge(strategy: str = "SPY_200d_trend_model") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "lane": "independent_family_challenge",
                "strategy": strategy,
                "family_id": "family_broad_etf_spy200d_v1",
                "run_status": "completed",
                "final_validation_completed": True,
                "credibility_tier": "tier3_candidate_validation",
                "audit_verdict": "benchmark_candidate",
            }
        ]
    )


def evaluate(summary: str, challenge: pd.DataFrame | None = None, rolling: pd.DataFrame | None = None, rankings: pd.DataFrame | None = None, tmp_path: Path | None = None):
    missing = tmp_path / "missing" if tmp_path else Path("missing")
    return consistency.evaluate_consistency(
        summary_text=summary,
        challenge=challenge if challenge is not None else completed_challenge(),
        rolling=rolling if rolling is not None else exact_rolling(),
        rankings=rankings if rankings is not None else pd.DataFrame(),
        advisor_texts={},
        advisor_latest=missing,
        challenge_latest=missing,
    )


def rule_ids(report: dict) -> set[str]:
    return {item["rule_id"] for item in report["errors"]}


def test_consistency_checker_script_exists() -> None:
    assert Path("run_advisor_consistency_check.py").exists()
    assert Path("advisor_audit/advisor_consistency_rules.yaml").exists()


def test_detects_benchmark_unavailable_contradiction(tmp_path: Path) -> None:
    summary = "ETF benchmark rolling rows are unavailable."
    report = evaluate(summary, rolling=exact_rolling("SPY_buy_hold"), challenge=completed_challenge("SPY_buy_hold"), tmp_path=tmp_path)
    assert "benchmark_availability_contradiction" in rule_ids(report)


def test_detects_spy_buy_hold_unavailable_contradiction(tmp_path: Path) -> None:
    summary = "SPY_buy_hold row unavailable."
    report = evaluate(summary, rolling=exact_rolling("SPY_buy_hold"), challenge=completed_challenge("SPY_buy_hold"), tmp_path=tmp_path)
    assert "spy_buy_hold_unavailable_contradiction" in rule_ids(report)


def test_detects_run_level_vs_row_level_finality_ambiguity(tmp_path: Path) -> None:
    summary = "- final_validation_completed: False"
    report = evaluate(summary, tmp_path=tmp_path)
    assert "run_level_vs_row_level_finality" in rule_ids(report)


def test_allows_run_level_false_when_row_level_finality_is_explained(tmp_path: Path) -> None:
    summary = "- final_validation_completed: False\nRun-level finality can be false while row-level exact evidence exists."
    report = evaluate(summary, tmp_path=tmp_path)
    assert "run_level_vs_row_level_finality" not in rule_ids(report)


def test_flags_incomplete_rows_with_populated_metrics(tmp_path: Path) -> None:
    challenge = pd.DataFrame(
        [
            {
                "strategy": "A_ETF_sector_momentum",
                "run_status": "incomplete_evidence",
                "unconditional_final_equity": 3301.0,
                "target_300_before_stop": True,
            }
        ]
    )
    report = evaluate("clean summary", challenge=challenge, rolling=pd.DataFrame(), tmp_path=tmp_path)
    assert "incomplete_rows_with_metrics" in rule_ids(report)


def test_flags_crypto_practical_candidate_violation(tmp_path: Path) -> None:
    rankings = pd.DataFrame(
        [
            {
                "lane": "independent_family_challenge",
                "strategy": "crypto_buy_hold_equal_weight",
                "family_id": "family_crypto_spot_buy_hold_equal_weight_v1",
                "family_group": "crypto_spot_buy_hold",
                "credibility_tier": "tier1_exploratory",
                "audit_verdict": "practical_candidate",
            }
        ]
    )
    report = evaluate("clean summary", challenge=pd.DataFrame(), rolling=pd.DataFrame(), rankings=rankings, tmp_path=tmp_path)
    assert "crypto_tier1_not_practical_candidate" in rule_ids(report)


def test_flags_real_money_recommendation_language(tmp_path: Path) -> None:
    report = evaluate("This strategy is real-money ready and guaranteed profit.", rolling=pd.DataFrame(), tmp_path=tmp_path)
    assert "real_money_boundary" in rule_ids(report)


def test_real_money_negation_is_allowed(tmp_path: Path) -> None:
    report = evaluate("This is not real-money suitable and has no guaranteed return.", rolling=pd.DataFrame(), tmp_path=tmp_path)
    assert "real_money_boundary" not in rule_ids(report)

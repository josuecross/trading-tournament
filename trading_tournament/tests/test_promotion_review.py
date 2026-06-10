from __future__ import annotations

import json
import zipfile
from pathlib import Path

import yaml


REVIEW_ROOT = Path("promotion_reviews/combo_SPY200d_GLD_50_50_v1")
LATEST_ROOT = Path("evidence/promotion_reviews/combo_SPY200d_GLD_50_50_v1/latest")
ZIP_PATH = Path("evidence/promotion_reviews/combo_SPY200d_GLD_50_50_v1/latest_promotion_review_packet.zip")
ALLOWED_DECISIONS = {
    "promote_to_paper_forward_review",
    "watchlist_more_evidence",
    "reject_for_now",
    "keep_as_research_candidate",
}


def load_registry() -> dict:
    return yaml.safe_load(Path("strategy_lab/strategy_registry.yaml").read_text(encoding="utf-8"))


def review_texts() -> list[str]:
    paths = list(REVIEW_ROOT.glob("*.md")) + list(LATEST_ROOT.glob("*.md"))
    return [path.read_text(encoding="utf-8") for path in paths]


def test_promotion_review_packet_exists_and_is_compact() -> None:
    assert REVIEW_ROOT.exists()
    assert LATEST_ROOT.exists()
    latest_files = [path.name for path in LATEST_ROOT.iterdir() if path.is_file()]
    assert len(latest_files) <= 10
    for name in [
        "README.md",
        "PROMOTION_REVIEW.md",
        "EVIDENCE_SUMMARY.md",
        "COMBO_VS_SPY200D.md",
        "COMBO_VS_TOP2.md",
        "RISK_REVIEW.md",
        "PAPER_FORWARD_READINESS_CHECKLIST.csv",
        "PROMOTION_DECISION.md",
        "promotion_review_manifest.json",
    ]:
        assert (REVIEW_ROOT / name).exists()
        assert (LATEST_ROOT / name).exists()
    assert ZIP_PATH.exists()
    with zipfile.ZipFile(ZIP_PATH) as zf:
        assert "PROMOTION_DECISION.md" in zf.namelist()
        assert "promotion_review_manifest.json" in zf.namelist()


def test_promotion_decision_is_allowed_and_boundary_flags_are_false() -> None:
    manifest = json.loads((LATEST_ROOT / "promotion_review_manifest.json").read_text(encoding="utf-8"))
    assert manifest["decision"] in ALLOWED_DECISIONS
    assert manifest["decision"] == "promote_to_paper_forward_review"
    assert manifest["paper_forward_active"] is False
    assert manifest["real_money_recommendation"] is False
    decision = (LATEST_ROOT / "PROMOTION_DECISION.md").read_text(encoding="utf-8")
    assert "Decision: `promote_to_paper_forward_review`" in decision
    assert "paper-forward activation" in decision


def test_promotion_review_has_required_comparison_files() -> None:
    combo_spy = (LATEST_ROOT / "COMBO_VS_SPY200D.md").read_text(encoding="utf-8")
    combo_top2 = (LATEST_ROOT / "COMBO_VS_TOP2.md").read_text(encoding="utf-8")
    risk = (LATEST_ROOT / "RISK_REVIEW.md").read_text(encoding="utf-8")
    checklist = (LATEST_ROOT / "PAPER_FORWARD_READINESS_CHECKLIST.csv").read_text(encoding="utf-8")
    assert "raw +300 or +400 target rates" in combo_spy
    assert "superior drawdown" in combo_spy
    assert "practical drawdown-aware leader" in combo_top2
    assert "Stop-Hit Comparison" in risk
    assert "fixed_rules_confirmed" in checklist
    assert "new_observation_id_required" in checklist
    assert "do_not_replace_spy200d_automatically" in checklist


def test_promotion_review_registry_row_does_not_activate_paper_forward() -> None:
    rows = load_registry()["strategies"]
    row = next(item for item in rows if item["id"] == "profit_combo_SPY200d_GLD_50_50_v1")
    assert row["status"] in {"promotion_review_passed", "active_paper_demo_observation"}
    assert row["allowed_next_action"] in {
        "create_new_paper_forward_observation_plan",
        "run_monthly_paper_forward_checkpoint",
    }
    assert row["paper_forward_active"] is (row["status"] == "active_paper_demo_observation")
    assert row["paper_forward_allowed_by_risk_framework"] is row["paper_forward_active"]
    assert row.get("real_money_recommendation", False) is not True
    assert (
        "observe_as_paper_forward_without_observation_plan" in row["forbidden_next_actions"]
        or "change_active_observation_rules_without_review" in row["forbidden_next_actions"]
    )
    assert "replace_spy200d_without_explicit_decision" in row["forbidden_next_actions"]


def test_promotion_review_makes_no_real_money_recommendation() -> None:
    for text in review_texts():
        lowered = text.lower()
        assert "real-money ready" not in lowered
        assert "recommended real trade" not in lowered
        assert "guaranteed" not in lowered
        assert "proven" not in lowered
        assert (
            "real-money recommendation" not in lowered
            or "no real-money recommendation" in lowered
            or "not a real-money recommendation" in lowered
            or "does not make a real-money recommendation" in lowered
            or "or make a real-money recommendation" in lowered
        )

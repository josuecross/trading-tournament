from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pandas as pd

from run_strategy_lab import DEFAULT_REGISTRY, load_registry, validate_registry_data


ROOT = Path(__file__).resolve().parents[1]
EXPANSION_DIR = ROOT / "historical_research_expansion"
LATEST_DIR = ROOT / "evidence" / "historical_research_expansion" / "latest"
EXPANSION_ZIP = ROOT / "evidence" / "historical_research_expansion" / "latest_historical_research_expansion_packet.zip"
PHASE = "historical_research_expansion_parallel_to_paper_demo_observation"


def test_historical_research_expansion_packet_exists_and_is_compact() -> None:
    assert EXPANSION_DIR.exists()
    assert LATEST_DIR.exists()
    assert len([p for p in LATEST_DIR.iterdir() if p.is_file()]) <= 10
    assert EXPANSION_ZIP.exists()
    with zipfile.ZipFile(EXPANSION_ZIP) as zf:
        names = set(zf.namelist())
    assert "CURRENT_PHASE_DECISION.md" in names
    assert "PAPER_FORWARD_SEPARATION_POLICY.md" in names
    assert "COMBINATION_DESIGN_GATE.md" in names


def test_current_phase_decision_corrects_checkpoint_misinterpretation() -> None:
    text = (EXPANSION_DIR / "CURRENT_PHASE_DECISION.md").read_text(encoding="utf-8")
    assert f"Current phase: `{PHASE}`" in text
    assert "Wait 30 trading days before doing more project work" in text
    assert "Wait 30 trading days before judging the forward observation, while continuing historical research in parallel" in text
    assert "SPY_200d` replaced: false" in text


def test_paper_forward_separation_policy_allows_historical_research() -> None:
    text = (EXPANSION_DIR / "PAPER_FORWARD_SEPARATION_POLICY.md").read_text(encoding="utf-8")
    assert "The paper-forward checkpoint clock does not freeze historical research" in text
    assert "run historical research_sample for new approved candidate" in text
    assert "create combination-design review | yes" in text
    assert "tune active combo | no" in text
    assert "replace SPY_200d | no" in text


def test_combination_design_gate_and_queues_are_review_only() -> None:
    gate = (EXPANSION_DIR / "COMBINATION_DESIGN_GATE.md").read_text(encoding="utf-8")
    assert "Maximum combinations per batch: `3`" in gate
    assert "Do not optimize weights after seeing results" in gate
    family_queue = pd.read_csv(EXPANSION_DIR / "HISTORICAL_CANDIDATE_FAMILY_QUEUE.csv")
    combo_queue = pd.read_csv(EXPANSION_DIR / "COMBINATION_CANDIDATE_QUEUE.csv")
    assert {
        "individual_stock_momentum_gate1b_v1",
        "crypto_spot_tsmom_tier2_review_v1",
        "managed_futures_proxy_combination_review_v1",
    }.issubset(set(family_queue["candidate_id"]))
    assert {
        "combo_plus_top2_50_50_review_v1",
        "combo_plus_managed_futures_80_20_review_v1",
        "top2_plus_managed_futures_80_20_review_v1",
    }.issubset(set(combo_queue["combination_id"]))
    assert family_queue["implementation_allowed_now"].astype(str).str.lower().eq("false").all()
    assert family_queue["backtest_allowed_now"].astype(str).str.lower().eq("false").all()
    assert combo_queue["research_sample_allowed_now"].astype(str).str.lower().eq("false").all()
    assert combo_queue["candidate_exhaustive_allowed_now"].astype(str).str.lower().eq("false").all()


def test_diagnostics_and_scoring_plans_exist() -> None:
    diagnostics = (EXPANSION_DIR / "DIAGNOSTICS_IMPROVEMENT_PLAN.md").read_text(encoding="utf-8")
    scoring = (EXPANSION_DIR / "EVIDENCE_AND_SCORING_IMPROVEMENT_PLAN.md").read_text(encoding="utf-8")
    assert "daily return correlation versus combo" in diagnostics
    assert "Drawdown Co-Incidence" in diagnostics
    assert "Fresh-Window Exactness Audit" in diagnostics
    assert "Separate profit-seeking score from practical stop-aware score" in scoring
    assert "Prevent target-rate-only ranking from dominating decisions" in scoring


def test_manifest_confirms_no_execution_or_download() -> None:
    manifest = json.loads((EXPANSION_DIR / "historical_research_manifest.json").read_text(encoding="utf-8"))
    assert manifest["current_phase"] == PHASE
    assert manifest["historical_research_parallel_allowed"] is True
    assert manifest["backtest_run"] is False
    assert manifest["profit_exploration_run"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["data_downloaded"] is False
    assert manifest["strategy_implemented"] is False
    assert manifest["real_money_recommendation"] is False


def test_strategy_lab_preserves_active_combo_and_frozen_spy_control() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    validation = validate_registry_data(data)
    assert validation["passed"] is True, validation
    combo = next(row for row in data["strategies"] if row["id"] == "profit_combo_SPY200d_GLD_50_50_v1")
    spy = next(row for row in data["strategies"] if row["id"] == "SPY_200d_trend_model")
    assert combo["status"] == "active_paper_demo_observation"
    assert combo["paper_forward_active"] is True
    assert combo["current_phase"] == PHASE
    assert combo["historical_research_parallel_allowed"] is True
    assert combo["forward_checkpoint_judgment_ready"] is False
    assert spy["rules_frozen"] is True
    assert spy["paper_forward_active"] is True


def test_no_recent_research_sample_candidate_added_to_candidate_exhaustive() -> None:
    queue = (ROOT / "candidate_triage" / "CANDIDATE_EXHAUSTIVE_QUEUE_REVIEW.md").read_text(encoding="utf-8")
    next_direction = (ROOT / "candidate_triage" / "NEXT_RESEARCH_DIRECTION.md").read_text(encoding="utf-8")
    assert "No recent research_sample candidate is added to candidate_exhaustive now." in queue
    assert "does not freeze historical research" in queue
    assert "Do not pause the historical research program itself" in next_direction
    assert "Create a combination-design implementation review" in next_direction


def test_no_real_money_or_strategy_implementation_language() -> None:
    combined = "\n".join(path.read_text(encoding="utf-8") for path in EXPANSION_DIR.iterdir() if path.is_file())
    assert "real-money recommendation" in combined
    assert "strategy_implemented\": false" in combined
    assert "backtest_run\": false" in combined
    assert "data_downloaded\": false" in combined

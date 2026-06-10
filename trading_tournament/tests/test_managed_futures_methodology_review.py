from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

import run_advisor_audit_packet as advisor_packet
from run_strategy_lab import DEFAULT_REGISTRY, load_registry, validate_registry_data


REVIEW_ID = "managed_futures_proxy_etf_trend_v1"
ROOT = Path("methodology_reviews") / REVIEW_ID
LATEST = Path("evidence/methodology_reviews") / REVIEW_ID / "latest"
ZIP_PATH = Path("evidence/methodology_reviews") / REVIEW_ID / "latest_methodology_review_packet.zip"
EXPECTED_FILES = {
    "README.md",
    "ISSUER_AND_FUND_IDENTITY_REVIEW.md",
    "METHODOLOGY_REVIEW.md",
    "WRAPPER_MODELING_ACCEPTANCE_REVIEW.md",
    "HISTORY_AND_REGIME_COVERAGE_REVIEW.md",
    "FEE_EXPENSE_AND_PRODUCT_RISK_REVIEW.md",
    "CORRELATION_AND_DIVERSIFICATION_REVIEW_PLAN.md",
    "BENCHMARK_AND_FAILURE_CRITERIA.md",
    "METHODOLOGY_DECISION.md",
    "methodology_review_manifest.json",
}
ALLOWED_DECISIONS = {
    "approve_research_sample_implementation_prompt",
    "conditional_approval_short_history_label_required",
    "methodology_review_passed_data_limited",
    "defer_methodology_or_identity_risk",
    "reject_proxy_not_suitable",
}


def test_methodology_review_packet_exists_and_is_compact() -> None:
    assert ROOT.exists()
    assert LATEST.exists()
    files = {path.name for path in LATEST.iterdir() if path.is_file()}
    assert len(files) <= 10
    assert files == EXPECTED_FILES
    assert ZIP_PATH.exists()
    with zipfile.ZipFile(ZIP_PATH) as zf:
        assert set(zf.namelist()) == files


def test_identity_methodology_and_history_sections_exist() -> None:
    identity = (LATEST / "ISSUER_AND_FUND_IDENTITY_REVIEW.md").read_text(encoding="utf-8")
    methodology = (LATEST / "METHODOLOGY_REVIEW.md").read_text(encoding="utf-8")
    wrapper = (LATEST / "WRAPPER_MODELING_ACCEPTANCE_REVIEW.md").read_text(encoding="utf-8")
    history = (LATEST / "HISTORY_AND_REGIME_COVERAGE_REVIEW.md").read_text(encoding="utf-8")
    fees = (LATEST / "FEE_EXPENSE_AND_PRODUCT_RISK_REVIEW.md").read_text(encoding="utf-8")
    benchmarks = (LATEST / "BENCHMARK_AND_FAILURE_CRITERIA.md").read_text(encoding="utf-8")
    for symbol in ["DBMF", "KMLM"]:
        assert symbol in identity
        assert symbol in methodology
        assert symbol in fees
    assert "wrapper identity confirmed" in identity
    assert "acceptable for research_sample proxy review" in identity
    assert "Wrapper-level ETF/fund price modeling is acceptable only for a future research_sample implementation prompt" in wrapper
    assert "2020-12-02 to 2026-05-29" in history
    assert "2008" in history
    assert "combo_SPY200d_GLD_50_50_v1" in benchmarks
    assert "asset_class_tsmom_top2_v1" in benchmarks


def test_methodology_decision_and_safety_flags() -> None:
    manifest = json.loads((LATEST / "methodology_review_manifest.json").read_text(encoding="utf-8"))
    decision = (LATEST / "METHODOLOGY_DECISION.md").read_text(encoding="utf-8")
    assert manifest["decision"] in ALLOWED_DECISIONS
    assert manifest["decision"] == "conditional_approval_short_history_label_required"
    assert "Decision: `conditional_approval_short_history_label_required`" in decision
    assert manifest["future_research_sample_implementation_prompt_approved"] is True
    assert manifest["required_label"] == "fund_wrapper_proxy_short_history_limited_inception_research_sample_only"
    assert manifest["wrapper_modeling_decision"] == "acceptable_for_research_sample_only"
    assert manifest["dbmf_identity_confirmed"] is True
    assert manifest["kmlm_identity_confirmed"] is True
    assert manifest["strategy_implemented"] is False
    assert manifest["backtest_run"] is False
    assert manifest["profit_exploration_run"] is False
    assert manifest["data_downloaded_in_this_task"] is False
    assert manifest["futures_contract_logic_added"] is False
    assert manifest["paper_forward_active"] is False
    assert manifest["paper_forward_rule_changed"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["raw_ohlcv_included"] is False


def test_no_strategy_backtest_profit_or_futures_code_created() -> None:
    run_profit = Path("run_profit_exploration.py").read_text(encoding="utf-8")
    specs = Path("profit_lab/profit_experiment_specs.yaml").read_text(encoding="utf-8")
    assert REVIEW_ID in run_profit
    assert REVIEW_ID in specs
    assert "run_backtest.py" not in run_profit
    source_files = [Path("run_backtest.py"), Path("run_report.py")]
    for source_file in source_files:
        assert source_file.exists()


def test_strategy_lab_status_after_methodology_review() -> None:
    data = load_registry(DEFAULT_REGISTRY)
    validation = validate_registry_data(data)
    assert validation["passed"], validation["errors"]
    row = next(item for item in data["strategies"] if item["id"] == REVIEW_ID)
    assert row["status"] in {"conditional_approval_short_history_label_required", "too_slow"}
    assert row["implementation_status"] in {"not_implemented", "implemented_research_sample"}
    assert row["allowed_next_action"] in {"create_research_sample_implementation_prompt", "research_sample_review"}
    assert row["paper_forward_active"] is False
    assert row["paper_forward_allowed_by_risk_framework"] is False
    assert row["real_money_recommendation"] is False
    for forbidden in [
        "observe_as_paper_forward",
        "promote_to_real_money",
        "add_broker_integration",
        "add_futures_contract_logic",
    ]:
        assert forbidden in row["forbidden_next_actions"]


def test_advisor_upload_references_methodology_review_without_new_top_zip(tmp_path: Path) -> None:
    latest = advisor_packet.build_all_packets(
        tmp_path / "advisor_upload",
        include_optional=True,
        include_repro_debug=True,
        strict=False,
        no_nested_zips=True,
    )["latest_dir"]
    top_files = [path.name for path in latest.iterdir() if path.is_file()]
    assert len(top_files) <= 10
    assert "09_METHODOLOGY_REVIEW.zip" not in top_files
    with zipfile.ZipFile(latest / "00_ADVISOR_INDEX.zip") as zf:
        review_index = zf.read("PROMOTION_IMPLEMENTATION_REVIEW_INDEX.csv").decode("utf-8")
        executive = zf.read("ADVISOR_EXECUTIVE_STATE.md").decode("utf-8")
    assert "managed_futures_proxy_methodology_review" in review_index
    assert "conditional_approval_short_history_label_required" in review_index
    assert "Managed-futures proxy methodology review packet:" in executive


def test_methodology_review_has_no_raw_data_secrets_or_real_money_claims() -> None:
    secret_patterns = [
        re.compile(r"sk-[A-Za-z0-9]{12,}"),
        re.compile(r"api[_-]?key\s*[:=]\s*['\"][A-Za-z0-9_\-]{12,}['\"]", re.IGNORECASE),
        re.compile(r"token\s*[:=]\s*['\"][A-Za-z0-9_\-]{12,}['\"]", re.IGNORECASE),
    ]
    for path in list(ROOT.rglob("*")) + list(LATEST.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".md", ".json"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        lower = text.lower()
        assert "raw ohlcv rows" not in lower
        assert "recommended real trade" not in lower
        assert "real-money ready" not in lower
        assert not any(pattern.search(text) for pattern in secret_patterns)

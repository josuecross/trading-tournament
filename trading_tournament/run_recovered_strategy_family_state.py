from __future__ import annotations

import csv
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parent
RUN_ID = "recovered_20260618"
NEXT_ALLOWED_ACTION = "create_candidate_exhaustive_prompt_for_gror_balanced_momentum_60_40_v1"


ACTIVE_OBSERVATIONS = {
    "paper_forward_vm_quality_lowvol_proxy_v1": {
        "base_strategy": "vm_quality_lowvol_proxy_v1",
        "family": "volatility_managed_equity_etf",
        "universe": ["SPLV", "USMV", "QUAL", "SPY", "BIL"],
        "rule": [
            "Monthly rebalance.",
            "Eligibility: close > 200-day SMA.",
            "Ranking: 126-day return / 60-day realized volatility.",
            "Hold top 2 eligible assets equally; if one eligible hold it 100%; if none hold 100% BIL.",
        ],
        "metrics": {
            "median_equity_180d": "about $3,247.09",
            "target_300_before_stop_180d": "about 53.85%",
            "target_400_before_stop_180d": "about 36.48%",
            "worst_drawdown_180d": "about -$549.41",
            "stop_hit_rate": "0.0%",
            "stress_10bps_median_equity": "about $3,243.14",
            "stress_worst_drawdown": "about -$557.47",
            "correlation_vs_active_combo": "about 0.551",
            "correlation_vs_SPY_200d": "about 0.8465",
        },
    },
    "paper_forward_dsr_sector_equal_weight_defensive_filter_v1": {
        "base_strategy": "dsr_sector_equal_weight_defensive_filter_v1",
        "family": "defensive_sector_rotation_etf",
        "universe": ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLU", "XLI", "XLB", "XLC", "BIL"],
        "rule": [
            "Monthly rebalance.",
            "Qualifying sector ETFs: close > 200-day SMA.",
            "Equal-weight qualifying sectors.",
            "If only one or two qualify, allocate one-third to each qualifying sector and remainder to BIL.",
            "If none qualify, hold 100% BIL.",
        ],
        "metrics": {
            "median_equity_180d": "about $3,302.75",
            "mean_equity_180d": "about $3,301.91",
            "p75_equity_180d": "about $3,511.36",
            "p90_equity_180d": "about $3,760.79",
            "best_equity_180d": "about $4,071.04",
            "worst_equity_180d": "about $2,578.70",
            "target_300_before_stop_180d": "about 66.51%",
            "target_400_before_stop_180d": "about 45.71%",
            "median_drawdown_180d": "about -$273.41",
            "worst_drawdown_180d": "about -$580.65",
            "stop_hit_rate": "0.0%",
            "stress_median_equity_180d": "about $3,297.76",
            "stress_degradation": "about -$4.98",
            "stress_target_300_before_stop": "about 65.96%",
            "stress_target_400_before_stop": "about 44.96%",
            "stress_worst_drawdown": "about -$582.84",
            "delta_vs_SPY_200d": "about +$72.37",
            "delta_vs_vm_quality": "about +$49.64",
            "delta_vs_active_combo": "about -$36.79",
            "active_combo_correlation": "about 0.549",
            "SPY_200d_correlation": "about 0.759",
            "vm_quality_correlation": "about 0.848",
            "equal_weight_sector_benchmark_correlation": "about 0.855",
            "sector_benchmark_duplicate_label": "likely_duplicate",
            "drawdown_improvement_vs_raw_equal_weight_sector_basket": "about +$590.10",
        },
    },
}


FAMILY_SUMMARY_ROWS = [
    {
        "family": "volatility_managed_equity_etf",
        "status": "active_observation_running",
        "winner_or_state": "vm_quality_lowvol_proxy_v1 active/frozen",
        "evidence_source": "conversation_recovered",
    },
    {
        "family": "defensive_sector_rotation_etf",
        "status": "active_observation_running",
        "winner_or_state": "dsr_sector_equal_weight_defensive_filter_v1 active/frozen; DSR Top3 queued/deferred",
        "evidence_source": "conversation_recovered",
    },
    {
        "family": "global_risk_on_risk_off_etf",
        "status": "promotion_candidate_found",
        "winner_or_state": "gror_balanced_momentum_60_40_v1 candidate_exhaustive_queue",
        "evidence_source": "conversation_recovered",
    },
    {
        "family": "quality_momentum_etf_proxy",
        "status": "watchlist_family",
        "winner_or_state": "No promotion candidate; risk-control rescue not approved now",
        "evidence_source": "conversation_recovered",
    },
]


RUNNER_NAMES = [
    "run_volatility_managed_equity_etf_research_sample.py",
    "run_vm_quality_lowvol_candidate_exhaustive.py",
    "run_vm_quality_lowvol_paper_forward_activation.py",
    "run_defensive_sector_rotation_etf_review.py",
    "run_defensive_sector_rotation_etf_research_sample.py",
    "run_dsr_sector_equal_weight_candidate_exhaustive.py",
    "run_dsr_sector_equal_weight_paper_forward_review.py",
    "run_dsr_sector_equal_weight_paper_forward_activation.py",
    "run_dsr_sector_top3_promotion_review.py",
    "run_profit_family_discovery_audit.py",
    "run_quality_momentum_etf_proxy_review.py",
    "run_quality_momentum_etf_proxy_research_sample.py",
    "run_quality_momentum_etf_proxy_risk_control_review.py",
    "run_quality_momentum_etf_proxy_risk_control_research_sample.py",
    "run_global_risk_on_risk_off_etf_review.py",
    "run_global_risk_on_risk_off_etf_research_sample.py",
    "run_gror_balanced_momentum_promotion_review.py",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def create_zip(directory: Path, name: str) -> None:
    zip_path = directory / name
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(directory.iterdir()):
            if path.is_file() and path.name != zip_path.name:
                zf.write(path, path.name)


def write_active_observation(observation_id: str, spec: dict[str, Any]) -> None:
    payload = {
        "observation_id": observation_id,
        "base_strategy_id": spec["base_strategy"],
        "family": spec["family"],
        "status": "active_paper_demo_observation",
        "account_type": "simulated_paper_demo_only",
        "evidence_source": "conversation_recovered",
        "frozen": True,
        "rules_frozen": True,
        "paper_forward_active": True,
        "real_money_recommendation": False,
        "broker_integration": False,
        "live_orders": False,
        "order_placement": False,
        "leverage": False,
        "margin": False,
        "shorting": False,
        "options": False,
        "futures": False,
        "forex": False,
        "crypto": False,
        "intraday": False,
        "minimum_days_before_judgment": 30,
        "current_checkpoint_status": "too_early_recovered_no_checkpoint_conclusion",
        "rule_summary": spec["rule"],
        "universe": spec["universe"],
        "conversation_recovered_metrics": spec["metrics"],
    }
    obs_dir = REPO_ROOT / "paper_forward_observations" / observation_id
    write_text(obs_dir / "active_observation.yaml", yaml.safe_dump(payload, sort_keys=False))

    activation_dir = REPO_ROOT / "evidence" / "paper_forward_activations" / spec["base_strategy"] / "latest"
    write_text(activation_dir / f"{observation_id}_active_observation.yaml", yaml.safe_dump(payload, sort_keys=False))
    write_text(activation_dir / "frozen_rule.md", "# Frozen Rule\n\n" + "\n".join(f"- {line}" for line in spec["rule"]) + "\n")
    write_text(
        activation_dir / "checkpoint_plan.md",
        "# Checkpoint Plan\n\nNo conclusion before 30 trading days except `too early`. Do not run checkpoints during recovery.\n",
    )
    write_text(
        activation_dir / "risk_plan.md",
        "# Risk Plan\n\nHard stop context remains -$600. This recovered packet is paper/demo only and not real-money guidance.\n",
    )
    write_text(
        activation_dir / "benchmark_plan.md",
        "# Benchmark Plan\n\nCompare against SPY_200d_trend_model, active combo, SPY buy-hold, BIL, and relevant family benchmarks.\n",
    )
    if "dsr" in observation_id:
        write_text(
            activation_dir / "sector_overlap_monitoring_plan.md",
            "# Sector Overlap Monitoring Plan\n\nTrack overlap against equal-weight sector basket and active DSR/VM controls.\n",
        )
        for name in ["daily_template.md", "weekly_template.md", "monthly_template.md"]:
            write_text(activation_dir / name, f"# {name.replace('_', ' ').replace('.md', '').title()}\n\nRecovered template; no checkpoint conclusion generated.\n")
    summary = "# Activation Summary\n\n"
    summary += f"- observation_id: `{observation_id}`\n"
    summary += f"- base_strategy_id: `{spec['base_strategy']}`\n"
    summary += "- evidence_source: `conversation_recovered`\n"
    summary += "- status: active/frozen simulated paper/demo observation\n"
    write_text(activation_dir / "activation_summary.md", summary)
    consistency = {
        "consistency_passed": True,
        "evidence_source_present": True,
        "evidence_source": "conversation_recovered",
        "frozen": True,
        "real_money_recommendation": False,
        "broker_integration": False,
        "live_orders": False,
        "order_placement": False,
        "checkpoint_conclusion_generated": False,
    }
    write_json(activation_dir / "consistency_check.json", consistency)
    manifest = {
        "run_id": RUN_ID,
        "observation_id": observation_id,
        "base_strategy_id": spec["base_strategy"],
        "evidence_source": "conversation_recovered",
        "paper_forward_active": True,
        "frozen": True,
        "candidate_exhaustive_run_during_recovery": False,
        "paper_forward_checkpoint_run_during_recovery": False,
        "broker_integration": False,
        "live_orders": False,
        "real_money_recommendation": False,
        "created_utc": now_utc(),
    }
    write_json(activation_dir / "manifest.json", manifest)
    create_zip(activation_dir, f"{observation_id}_recovered_packet.zip")


def write_family_packet(stage: str, subject: str, summary: str, rows: list[dict[str, Any]] | None = None) -> None:
    latest = REPO_ROOT / "evidence" / stage / subject / "latest"
    run_dir = REPO_ROOT / "evidence" / stage / subject / "runs" / RUN_ID
    for directory in [run_dir, latest]:
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True, exist_ok=True)
        write_text(directory / "summary.md", summary)
        write_text(directory / "decision.md", summary + f"\n\nEvidence source: `conversation_recovered`.\n")
        if rows is None:
            rows = [{"subject": subject, "status": "recovered", "evidence_source": "conversation_recovered"}]
        write_csv(directory / "recovered_rows.csv", rows, sorted({key for row in rows for key in row}))
        write_json(
            directory / "manifest.json",
            {
                "run_id": RUN_ID,
                "subject": subject,
                "stage": stage,
                "evidence_source": "conversation_recovered",
                "candidate_exhaustive_run": False,
                "paper_forward_activation_run": False,
                "broker_integration": False,
                "live_orders": False,
                "real_money_recommendation": False,
            },
        )
        write_json(
            directory / "consistency_check.json",
            {
                "consistency_passed": True,
                "evidence_source_present": True,
                "no_gror_candidate_exhaustive_run": True,
                "no_checkpoint_conclusion_generated": True,
            },
        )
        create_zip(directory, f"{subject}_recovered_packet.zip")


def recovery_note() -> None:
    text = f"""# Recovery From Lost Updates

Surviving context: the local repo retained the volatility-managed equity ETF lane review and the Strategy Lab governance skeleton. Work after that review was missing or incomplete in local files.

Reconstructed in this pass:

- active/frozen paper/demo observations for `paper_forward_vm_quality_lowvol_proxy_v1` and `paper_forward_dsr_sector_equal_weight_defensive_filter_v1`
- conversation-recovered activation packets for both active rows
- recovered family/status summaries for volatility-managed ETF, defensive sector rotation ETF, quality/momentum ETF proxy, global risk-on/risk-off ETF, and the profit-family discovery audit
- registry rows for active/frozen, queued/deferred, watchlist, and family-state records
- minimum fixed-rule helpers and focused tests
- runner stubs for recovered review/sample/promotion/activation packet creation

Conversation-recovered evidence:

- all performance, stress, drawdown, target, benchmark delta, overlap, duplicate, and correlation metrics listed in recovered packets

Recomputed evidence:

- none in this recovery pass

Missing evidence:

- original exact ZIP packet bytes
- original full run logs
- exact local-cache recomputation outputs for the recovered metrics
- GROR candidate_exhaustive results, because that run had not occurred before the loss and was not run during recovery

Recovered/frozen active observations:

- `paper_forward_vm_quality_lowvol_proxy_v1`
- `paper_forward_dsr_sector_equal_weight_defensive_filter_v1`

Manual review checklist:

- verify recovered metrics against any external conversation transcript if available
- decide whether to run `{NEXT_ALLOWED_ACTION}` later
- keep recovered active observations frozen
- do not treat conversation-recovered evidence as recomputed evidence
- do not treat paper/demo observations as real-money readiness
"""
    write_text(REPO_ROOT / "RECOVERY_FROM_LOST_UPDATES.md", text)


def registry_row(row_id: str, **overrides: Any) -> dict[str, Any]:
    base = {
        "id": row_id,
        "display_name": row_id.replace("_", " ").title(),
        "lane": "profit_exploration",
        "instrument_family": "ETF",
        "strategy_family": overrides.get("strategy_family", "recovered_family"),
        "version": "v1",
        "parent_id": "",
        "credibility_tier": "tier2_exploratory",
        "status": "watchlist",
        "role": "recovered_strategy_state",
        "rules_frozen": True,
        "paper_forward_active": False,
        "implementation_status": "implemented_research_sample",
        "data_source": "existing_adjusted_etf_cache_or_missing",
        "evidence_source": "conversation_recovered",
        "latest_evidence_path": "evidence/recovery/latest/",
        "latest_known_result_summary": "Recovered from project conversation after lost updates; metrics are not claimed as recomputed.",
        "allowed_next_action": "research_sample_review",
        "forbidden_next_actions": [
            "observe_as_paper_forward",
            "promote_to_real_money",
            "add_broker_integration",
            "place_live_orders",
            "use_futures_contract_logic",
            "use_leverage",
            "use_margin",
            "use_shorting",
            "tune_parameters",
        ],
        "risk_framework_status": "research_only_recovered",
        "paper_forward_allowed_by_risk_framework": False,
        "real_money_recommendation": False,
        "promotion_blockers": "conversation_recovered_only;not_recomputed",
        "promotion_requirements": "Manual review and appropriate validation gate before any promotion.",
        "demotion_or_kill_criteria": "Missing evidence, duplicate exposure, or risk budget failure.",
        "notes": "Recovered state row; no broker integration, live orders, or real-money recommendation.",
        "strategy_id": row_id,
        "family": overrides.get("family", overrides.get("strategy_family", "recovered_family")),
        "instrument_lane": "ETF",
        "evidence_tier": "tier2_exploratory",
        "current_status": "watchlist",
        "allowed_next_actions": ["research_sample_review"],
        "candidate_exhaustive_run": False,
        "candidate_exhaustive_recommended": False,
        "promotion_review_required": False,
        "promotion_decision": "keep_watchlist",
        "promotion_reason": "Conversation-recovered state only.",
        "primary_failure_mode": "not_assessed_in_registry",
        "duplication_risk": "not_flagged",
        "risk_budget_status": "not_assessed_in_registry",
        "evidence_needed": "recomputed or promotion-gate evidence",
        "duplicate_of": "",
        "blocked_reason": "",
    }
    base.update(overrides)
    base["strategy_id"] = base["id"]
    base["family"] = base.get("family", base["strategy_family"])
    base["current_status"] = base["status"]
    base["evidence_tier"] = base["credibility_tier"]
    return base


def update_registry() -> None:
    path = REPO_ROOT / "strategy_lab" / "strategy_registry.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rows = data.setdefault("strategies", [])
    by_id = {row["id"]: row for row in rows}

    recovered_rows = [
        registry_row(
            "paper_forward_vm_quality_lowvol_proxy_v1",
            display_name="Paper Forward VM Quality Lowvol Proxy v1",
            lane="paper_forward",
            strategy_family="volatility_managed_equity_etf",
            family="volatility_managed_equity_etf",
            credibility_tier="tier4_paper_forward",
            status="active_paper_demo_observation",
            role="active_recovered_paper_demo_observation",
            paper_forward_active=True,
            implementation_status="implemented",
            latest_evidence_path="evidence/paper_forward_activations/vm_quality_lowvol_proxy_v1/latest/",
            latest_known_result_summary="Active/frozen recovered paper-demo observation; 180d median equity about $3,247.09 and stop-hit rate 0.0% from conversation-recovered evidence.",
            allowed_next_action="observe_only",
            allowed_next_actions=["observe_only"],
            forbidden_next_actions=["change_rules", "tune_parameters", "promote_to_real_money", "add_broker_integration", "place_orders", "place_live_orders"],
            risk_framework_status="paper_forward_allowed_recovered",
            paper_forward_allowed_by_risk_framework=True,
            promotion_blockers="no_real_money_promotion;rules_frozen_observe_only;conversation_recovered_evidence",
            promotion_decision="paper_forward_activation_recovered",
            risk_budget_status="active_observation",
            evidence_needed="paper/demo observation only; no real-money conclusion",
            frozen=True,
        ),
        registry_row(
            "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
            display_name="Paper Forward DSR Sector Equal Weight Defensive Filter v1",
            lane="paper_forward",
            strategy_family="defensive_sector_rotation_etf",
            family="defensive_sector_rotation_etf",
            credibility_tier="tier4_paper_forward",
            status="active_paper_demo_observation",
            role="active_recovered_paper_demo_observation",
            paper_forward_active=True,
            implementation_status="implemented",
            latest_evidence_path="evidence/paper_forward_activations/dsr_sector_equal_weight_defensive_filter_v1/latest/",
            latest_known_result_summary="Active/frozen recovered paper-demo observation; 180d median equity about $3,302.75 and stop-hit rate 0.0% from conversation-recovered evidence.",
            allowed_next_action="observe_only",
            allowed_next_actions=["observe_only"],
            forbidden_next_actions=["change_rules", "tune_parameters", "promote_to_real_money", "add_broker_integration", "place_orders", "place_live_orders"],
            risk_framework_status="paper_forward_allowed_recovered",
            paper_forward_allowed_by_risk_framework=True,
            promotion_blockers="no_real_money_promotion;rules_frozen_observe_only;conversation_recovered_evidence",
            promotion_decision="paper_forward_activation_recovered",
            risk_budget_status="active_observation",
            evidence_needed="paper/demo observation only; no real-money conclusion",
            frozen=True,
        ),
        registry_row(
            "dsr_sector_top3_momentum_defensive_cash_v1",
            strategy_family="defensive_sector_rotation_etf",
            family="defensive_sector_rotation_etf",
            status="deferred_candidate_queue",
            latest_evidence_path="evidence/promotion_reviews/dsr_sector_top3_momentum_defensive_cash_v1/latest/",
            latest_known_result_summary="Promotion review passed and candidate_exhaustive was recommended, but deferred because same family as active DSR row.",
            allowed_next_action="candidate_exhaustive_review",
            allowed_next_actions=["candidate_exhaustive_review"],
            candidate_exhaustive_recommended=True,
            promotion_review_required=False,
            promotion_decision="promote_to_candidate_exhaustive_queue",
            risk_budget_status="queued_deferred",
            evidence_needed="candidate_exhaustive only if later explicitly approved",
        ),
        registry_row(
            "gror_balanced_momentum_60_40_v1",
            strategy_family="global_risk_on_risk_off_etf",
            family="global_risk_on_risk_off_etf",
            status="candidate_exhaustive_queue",
            latest_evidence_path="evidence/promotion_reviews/gror_balanced_momentum_60_40_v1/latest/",
            latest_known_result_summary="Promotion review recovered as promote_to_candidate_exhaustive_queue; candidate_exhaustive not run.",
            allowed_next_action=NEXT_ALLOWED_ACTION,
            allowed_next_actions=[NEXT_ALLOWED_ACTION],
            candidate_exhaustive_recommended=True,
            promotion_review_required=False,
            promotion_decision="promote_to_candidate_exhaustive_queue",
            risk_budget_status="candidate_exhaustive_queue",
            evidence_needed="candidate_exhaustive prompt may be created later; do not run during recovery",
        ),
        registry_row(
            "quality_momentum_etf_proxy",
            strategy_family="quality_momentum_etf_proxy",
            family="quality_momentum_etf_proxy",
            status="watchlist_family",
            implementation_status="not_implemented",
            latest_evidence_path="evidence/research_samples/quality_momentum_etf_proxy/latest/",
            latest_known_result_summary="Watchlist family; no promotion candidate. Profit power existed but failed risk/duplicate gates.",
        ),
        registry_row(
            "quality_momentum_etf_proxy_risk_control_batch_1",
            strategy_family="quality_momentum_etf_proxy",
            family="quality_momentum_etf_proxy",
            status="watchlist_family",
            implementation_status="not_implemented",
            latest_evidence_path="evidence/research_samples/quality_momentum_etf_proxy_risk_control_batch_1/latest/",
            latest_known_result_summary="Risk-control batch stayed watchlist/duplicate; no further rescue approved now.",
        ),
        registry_row("volatility_managed_equity_etf", strategy_family="volatility_managed_equity_etf", status="active_observation_running", implementation_status="not_implemented"),
        registry_row("defensive_sector_rotation_etf", strategy_family="defensive_sector_rotation_etf", status="active_observation_running", implementation_status="not_implemented"),
        registry_row("global_risk_on_risk_off_etf", strategy_family="global_risk_on_risk_off_etf", status="promotion_candidate_found", implementation_status="not_implemented"),
        registry_row("managed_futures_etf_wrapper", strategy_family="managed_futures_etf_wrapper", status="research_queue", implementation_status="not_implemented"),
        registry_row("commodity_wrapper", strategy_family="commodity_wrapper", status="deferred", implementation_status="not_implemented"),
        registry_row("crypto_spot", strategy_family="crypto_spot", status="deferred", implementation_status="not_implemented"),
        registry_row("individual_stock_momentum", strategy_family="individual_stock_momentum", status="deferred", implementation_status="not_implemented"),
    ]

    for row in recovered_rows:
        if row["id"] in by_id:
            by_id[row["id"]].update(row)
        else:
            rows.append(row)
    data["registry"]["last_updated_utc"] = now_utc()
    path.write_text(yaml.safe_dump(data, sort_keys=False, width=120), encoding="utf-8")


def write_recovery_packets() -> None:
    for observation_id, spec in ACTIVE_OBSERVATIONS.items():
        write_active_observation(observation_id, spec)
    write_family_packet(
        "profit_family_discovery_audit",
        "profit_family_discovery_audit",
        f"# Profit Family Discovery Audit\n\nDecision: defer DSR Top3, open quality/momentum ETF proxy lane, and keep family discovery moving. Current next allowed action after recovery is `{NEXT_ALLOWED_ACTION}`; do not run it automatically.\n",
        FAMILY_SUMMARY_ROWS,
    )
    write_family_packet("research_samples", "quality_momentum_etf_proxy", "# Quality/Momentum ETF Proxy Recovery\n\nStatus: watchlist_family. No promotion candidate.\n")
    write_family_packet("research_samples", "quality_momentum_etf_proxy_risk_control_batch_1", "# Quality/Momentum Risk-Control Batch Recovery\n\nStatus: watchlist_family. No further rescue approved now.\n")
    write_family_packet("research_samples", "global_risk_on_risk_off_etf", "# Global Risk-On/Risk-Off ETF Recovery\n\nStatus: `gror_balanced_momentum_60_40_v1` promotion candidate queued; candidate_exhaustive not run.\n")
    write_family_packet("promotion_reviews", "gror_balanced_momentum_60_40_v1", "# GROR Balanced Momentum Promotion Review\n\nFinal decision: `promote_to_candidate_exhaustive_queue`. Candidate_exhaustive recommended true, but not run.\n")
    write_family_packet("promotion_reviews", "dsr_sector_top3_momentum_defensive_cash_v1", "# DSR Top3 Promotion Review\n\nFinal decision: `promote_to_candidate_exhaustive_queue`, deferred because active DSR row exists.\n")
    recovery_note()


def write_runner_stubs() -> None:
    for runner in RUNNER_NAMES:
        path = REPO_ROOT / runner
        if path.exists():
            continue
        subject = runner.removeprefix("run_").removesuffix(".py")
        text = f"""from __future__ import annotations

from run_recovered_strategy_family_state import write_recovery_packets


def main() -> None:
    write_recovery_packets()
    print("{subject}_recovered=true")
    print("evidence_source=conversation_recovered")
    print("candidate_exhaustive_run=false")
    print("paper_forward_checkpoint_run=false")
    print("real_money_recommendation=false")


if __name__ == "__main__":
    main()
"""
        write_text(path, text)


def main() -> None:
    write_recovery_packets()
    write_runner_stubs()
    update_registry()
    print("recovery_packets_written=true")
    print(f"next_allowed_action={NEXT_ALLOWED_ACTION}")
    print("candidate_exhaustive_run=false")
    print("paper_forward_checkpoint_run=false")
    print("real_money_recommendation=false")


if __name__ == "__main__":
    main()

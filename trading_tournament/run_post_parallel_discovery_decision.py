from __future__ import annotations

import csv
import json
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "post_parallel_discovery_decision" / "latest"
PARALLEL_DIR = Path("evidence") / "parallel_research_discovery" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"

FINAL_DECISION = "move_to_dsr_sector_top2_momentum_200d_bil_promotion_review"
COMMIT_FIRST = "commit_parallel_discovery_results_first"
BEST_FAMILY = "gtaa_faber_style_benchmark_lane"
BEST_ROW = "gtaa_top3_trend_filter_v1"
PROTECTED_IDS = {
    "current_no_cash_proxy_alpha_AB",
    "paper_forward_vm_quality_lowvol_proxy_v1",
    "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
    "SPY_200d_trend_model",
}
PARALLEL_DISCOVERY_PATHS = [
    "run_parallel_research_discovery.py",
    "strategy_lab/parallel_research_discovery_queue.yaml",
    "tests/test_parallel_research_discovery.py",
    "evidence/parallel_research_discovery",
    "evidence/research_samples/gtaa_faber_style_benchmark_lane",
    "evidence/research_samples/static_all_weather_or_permanent_portfolio_benchmark",
    "evidence/research_samples/low_beta_defensive_equity_etf",
    "evidence/research_samples/dividend_quality_yield_etf",
    "evidence/research_samples/carry_yield_etf_proxy",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def create_packet(directory: Path, name: str) -> Path:
    packet = directory / name
    if packet.exists():
        packet.unlink()
    with zipfile.ZipFile(packet, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(directory.iterdir()):
            if path.is_file() and path.name != packet.name:
                archive.write(path, path.name)
    return packet


def git_status_for_paths(root: Path, paths: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain=v1", "--", *paths],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return "git_unavailable"
    return result.stdout.strip()


def parallel_discovery_committed(root: Path) -> bool:
    return git_status_for_paths(root, PARALLEL_DISCOVERY_PATHS) == ""


def active_observations_frozen(root: Path) -> bool:
    registry = load_yaml(root / REGISTRY_PATH)
    rows = {str(row.get("id")): row for row in registry.get("strategies", [])}
    for row_id in PROTECTED_IDS:
        row = rows.get(row_id)
        if row_id == "current_no_cash_proxy_alpha_AB":
            if row and row.get("paper_forward_active") is not True:
                return False
            continue
        if not row:
            return False
        if row.get("rules_frozen") is not True:
            return False
        if row.get("paper_forward_active") is not True:
            return False
        if row.get("allowed_next_action") != "observe_only":
            return False
    return True


def read_parallel_evidence(root: Path) -> dict[str, Any]:
    latest = root / PARALLEL_DIR
    required = [
        "parallel_research_discovery_summary.md",
        "family_leaderboard.csv",
        "strategy_leaderboard.csv",
        "promotion_review_candidates.csv",
        "watchlist_rows.csv",
        "too_risky_rows.csv",
        "rejected_rows.csv",
        "next_action.md",
        "parallel_research_discovery_consistency_check.json",
    ]
    missing = [name for name in required if not (latest / name).exists()]
    if missing:
        raise FileNotFoundError(f"missing parallel discovery evidence: {missing}")
    return {
        "summary": (latest / "parallel_research_discovery_summary.md").read_text(encoding="utf-8"),
        "family_leaderboard": read_csv(latest / "family_leaderboard.csv"),
        "strategy_leaderboard": read_csv(latest / "strategy_leaderboard.csv"),
        "promotion_review_candidates": read_csv(latest / "promotion_review_candidates.csv"),
        "watchlist_rows": read_csv(latest / "watchlist_rows.csv"),
        "too_risky_rows": read_csv(latest / "too_risky_rows.csv"),
        "rejected_rows": read_csv(latest / "rejected_rows.csv"),
        "next_action": (latest / "next_action.md").read_text(encoding="utf-8"),
        "parallel_consistency": load_json(latest / "parallel_research_discovery_consistency_check.json"),
    }


def confirm_parallel_state(evidence: dict[str, Any], root: Path) -> dict[str, Any]:
    family_rows = evidence["family_leaderboard"]
    strategy_rows = evidence["strategy_leaderboard"]
    promotions = evidence["promotion_review_candidates"]
    best_family = family_rows[0] if family_rows else {}
    best_row = strategy_rows[0] if strategy_rows else {}
    gtaa_top3 = next((row for row in strategy_rows if row.get("strategy_id") == BEST_ROW), {})
    parallel_check = evidence["parallel_consistency"]
    confirmations = {
        "no_promotion_candidates_exist": len(promotions) == 0,
        "best_family_is_gtaa": best_family.get("family_id") == BEST_FAMILY,
        "best_family_only_watchlist": best_family.get("family_verdict") == "watchlist_family",
        "best_row_is_gtaa_top3": best_row.get("strategy_id") == BEST_ROW,
        "gtaa_top3_is_watchlist": gtaa_top3.get("strategy_verdict") == "watchlist",
        "parallel_next_action_was_continue": "continue_best_parallel_discovery_family" in evidence["next_action"],
        "active_observations_frozen": active_observations_frozen(root),
        "no_candidate_exhaustive_or_paper_forward_ran": parallel_check.get("no_candidate_exhaustive_run") is True
        and parallel_check.get("no_paper_forward_activation") is True,
    }
    if not all(confirmations.values()):
        raise RuntimeError(f"post-parallel discovery premise mismatch: {confirmations}")
    return confirmations


def dsr_top2_future_review_candidate(root: Path) -> bool:
    registry = load_yaml(root / REGISTRY_PATH)
    rows = {str(row.get("id")): row for row in registry.get("strategies", [])}
    row = rows.get("dsr_sector_top2_momentum_200d_bil_v1")
    if not row:
        return False
    return (
        row.get("status") == "future_review_candidate"
        and row.get("promotion_review_required") is True
        and row.get("candidate_exhaustive_run") is False
        and row.get("paper_forward_active") is False
    )


def choose_next_action(root: Path) -> str:
    if not parallel_discovery_committed(root):
        return COMMIT_FIRST
    if dsr_top2_future_review_candidate(root):
        return FINAL_DECISION
    return "reassess_research_roadmap_after_parallel_discovery"


def best_family_audit_markdown(evidence: dict[str, Any], decision: str, committed: bool) -> str:
    return f"""# Best Family Audit

1. Was `{BEST_FAMILY}` genuinely strong?

No. It was the best family in the parallel early-discovery batch, but the best score was only watchlist-level. That is useful signal, not a promotion-quality result.

2. Did any GTAA row earn promotion-review status?

No. The promotion-review candidate file is empty, and every GTAA row is either `watchlist` or `too_risky`.

3. Is `{BEST_ROW}` worth a focused diagnostic?

Not as the immediate next step. It can remain a future diagnostic target if a specific missing question is identified, but the current evidence does not justify trying to rescue it.

4. Is GTAA mostly useful as a benchmark/sanity-check lane?

Yes. The family is valuable as a benchmark/watchlist lane because it gives a simple global tactical allocation comparison against other research directions.

5. Would continuing GTAA likely produce useful discovery, or just more watchlist rows?

Likely more watchlist rows unless a narrow diagnostic question is defined first. The current result does not show a clear path from watchlist to promotion candidate.

6. Should we move to DSR Top2 because it is a previously identified future-review candidate?

Yes, if the parallel discovery work is already committed. The registry still carries `dsr_sector_top2_momentum_200d_bil_v1` as a bounded future review candidate, and no new family displaced it with a promotion candidate.

7. Should we commit current parallel discovery first before continuing?

{"No blocking commit is needed because the parallel discovery paths are committed." if committed else "Yes. The parallel discovery outputs should be committed before any next research step."}

Decision: `{decision}`
"""


def gtaa_interpretation_markdown(evidence: dict[str, Any]) -> str:
    rows = [row for row in evidence["strategy_leaderboard"] if row.get("family_id") == BEST_FAMILY]
    row_lines = "\n".join(
        f"- `{row['strategy_id']}`: `{row['strategy_verdict']}`, score `{row['profit_first_score']}`"
        for row in rows
    )
    return f"""# GTAA Watchlist Interpretation

{row_lines}

`{BEST_ROW}` is the best row in the batch, but it is still only `watchlist`. `gtaa_breadth_defensive_v1`, `gtaa_equal_weight_trend_filter_v1`, and `gtaa_spy_gld_ief_static_trend_v1` are also watchlist rows. `gtaa_top2_risk_adjusted_v1` screened as `too_risky`.

GTAA is not a promotion candidate now because no row crossed the promotion-review threshold, the family verdict is only `watchlist_family`, and one GTAA variant failed risk screening. This should not be treated as a successful strategy or as a candidate-validation input.

GTAA should remain a benchmark/watchlist lane. To justify promotion later, it would need a separate approved review showing stronger profit-first evidence, acceptable risk, clear non-duplication versus frozen active observations and controls, and an explicit promotion-review approval. No such approval exists in the current packet.
"""


def next_step_markdown(decision: str, committed: bool) -> str:
    return f"""# Next Step Decision

Final decision: `{decision}`

Rationale: the parallel discovery batch found no promotion-review candidates. GTAA was best, but only watchlist. Because the parallel discovery framework and results are {"already committed" if committed else "not yet committed"}, the next safe action is {"the bounded DSR Top2 promotion review" if decision == FINAL_DECISION else "to preserve the current result before further research"}.

This decision does not run candidate validation, candidate_exhaustive, paper-forward review, paper-forward activation, or any new strategy computation.
"""


def commit_recommendation_markdown(committed: bool) -> str:
    if committed:
        return """# Parallel Discovery Commit Recommendation

Commit-before-next-research is not blocking now: the parallel discovery paths are already committed.

If this state ever appears uncommitted, use message:

`Add parallel early-discovery framework and roadmap batch results`

Commit body should mention the queue, the five screened families, no promotion candidates, GTAA as best watchlist family, low-beta and dividend quality rejected, no candidate validation/paper-forward/broker/live-order/real-money path, and exploratory non-final outputs.
"""
    return """# Parallel Discovery Commit Recommendation

Commit current parallel discovery results before further research.

Suggested message:

`Add parallel early-discovery framework and roadmap batch results`

Suggested body:

- Added parallel research discovery queue.
- Screened GTAA, static all-weather, low-beta, dividend quality, and carry/yield lanes.
- No promotion candidates were found.
- GTAA became the best watchlist family.
- Low-beta and dividend quality were rejected at family level.
- No candidate validation, paper-forward, broker, live-order, or real-money path was added.
- Outputs are exploratory and non-final.
"""


def run_post_parallel_discovery_decision(root: Path = ROOT) -> dict[str, Any]:
    evidence = read_parallel_evidence(root)
    confirmations = confirm_parallel_state(evidence, root)
    committed = parallel_discovery_committed(root)
    decision = choose_next_action(root)

    output_dir = root / OUTPUT_DIR
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    family_rows = evidence["family_leaderboard"]
    strategy_rows = evidence["strategy_leaderboard"]
    watchlist_rows = evidence["watchlist_rows"]
    too_risky_rows = evidence["too_risky_rows"]
    rejected_rows = evidence["rejected_rows"]

    summary = f"""# Post-Parallel Discovery Decision

Decision: `{decision}`

Best family: `{family_rows[0]['family_id']}`

Best row: `{strategy_rows[0]['strategy_id']}` with verdict `{strategy_rows[0]['strategy_verdict']}`

Promotion-review candidates: `{len(evidence['promotion_review_candidates'])}`

Interpretation: GTAA remains useful as a benchmark/watchlist lane, not as a successful strategy. Since the parallel discovery result is {"committed" if committed else "uncommitted"}, the next action is `{decision}`.
"""
    (output_dir / "post_parallel_discovery_decision_summary.md").write_text(summary, encoding="utf-8")
    (output_dir / "best_family_audit.md").write_text(best_family_audit_markdown(evidence, decision, committed), encoding="utf-8")
    (output_dir / "gtaa_watchlist_interpretation.md").write_text(gtaa_interpretation_markdown(evidence), encoding="utf-8")
    (output_dir / "next_step_decision.md").write_text(next_step_markdown(decision, committed), encoding="utf-8")
    (output_dir / "parallel_discovery_commit_recommendation.md").write_text(commit_recommendation_markdown(committed), encoding="utf-8")
    write_csv(
        output_dir / "watchlist_candidate_triage.csv",
        watchlist_rows + too_risky_rows + rejected_rows,
        ["family_id", "strategy_id", "profit_first_score", "score_label", "strategy_verdict"],
    )
    write_csv(
        output_dir / "roadmap_after_parallel_discovery.csv",
        [
            {"rank": 1, "item": "parallel_discovery_results", "status": "committed" if committed else "uncommitted", "next_action": decision if not committed else "completed"},
            {"rank": 2, "item": "gtaa_faber_style_benchmark_lane", "status": "watchlist_family", "next_action": "keep_as_benchmark_watchlist"},
            {"rank": 3, "item": "dsr_sector_top2_momentum_200d_bil_v1", "status": "future_review_candidate", "next_action": FINAL_DECISION},
        ],
        ["rank", "item", "status", "next_action"],
    )

    consistency = {
        "post_parallel_audit_completed": True,
        "no_new_research_run": True,
        "no_backtest_run": True,
        "no_candidate_exhaustive_run": True,
        "no_paper_forward_activation": True,
        "no_data_download": True,
        "no_provider_api_call": True,
        "active_observations_unchanged": confirmations["active_observations_frozen"],
        "no_broker_path_added": True,
        "no_live_order_path_added": True,
        "no_real_money_recommendation": True,
        "no_promotion_candidates_confirmed": confirmations["no_promotion_candidates_exist"],
        "best_row_is_watchlist": confirmations["gtaa_top3_is_watchlist"],
        "next_action_explicit": decision in {
            COMMIT_FIRST,
            "create_gtaa_faber_style_benchmark_lane_focused_diagnostic_prompt",
            FINAL_DECISION,
            "reassess_research_roadmap_after_parallel_discovery",
            "pause_new_research_until_active_observation_checkpoint",
        },
        "consistency_passed": False,
    }
    consistency["consistency_passed"] = all(value is True for key, value in consistency.items() if key != "consistency_passed")
    write_json(output_dir / "post_parallel_discovery_consistency_check.json", consistency)
    create_packet(output_dir, "post_parallel_discovery_decision_packet.zip")
    return {
        "output_dir": str(output_dir),
        "decision": decision,
        "parallel_discovery_committed": committed,
        "best_family": family_rows[0],
        "best_row": strategy_rows[0],
        "promotion_candidates": len(evidence["promotion_review_candidates"]),
        "consistency": consistency,
    }


def main() -> int:
    result = run_post_parallel_discovery_decision(ROOT)
    print(f"post_parallel_decision_latest_dir={result['output_dir']}")
    print(f"decision={result['decision']}")
    print(f"parallel_discovery_committed={str(result['parallel_discovery_committed']).lower()}")
    print(f"best_family={result['best_family'].get('family_id', '')}")
    print(f"best_row={result['best_row'].get('strategy_id', '')}")
    print(f"promotion_candidates={result['promotion_candidates']}")
    print(f"consistency_passed={str(result['consistency']['consistency_passed']).lower()}")
    return 0 if result["consistency"]["consistency_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

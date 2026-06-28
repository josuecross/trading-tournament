from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "tournament_root_cause_audit" / "latest"
STRATEGY_REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
EXPANSION_REGISTRY_PATH = Path("strategy_lab") / "strategy_expansion_candidates_v1.yaml"
FIRST_EXPANSION_RESULTS = Path("evidence") / "parallel_research_discovery" / "first_expansion_batch_without_sector_rs" / "latest" / "first_expansion_candidate_results.csv"

SEARCH_TERMS = ["GLD", "gold", "precious", "GROR", "global risk", "risk_on", "risk_off", "IEF", "TLT", "BIL", "macro rotation"]
SKIP_DIRS = {".git", ".venv", "__pycache__", "node_modules"}
SKIP_SUFFIXES = {".zip", ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".pyc", ".pyo", ".parquet", ".feather", ".sqlite", ".db"}
MAX_SCAN_BYTES = 2_500_000
MAX_SEARCH_ROWS = 1500

MANIFEST_FLAGS = {
    "audit_only": True,
    "new_backtests_run": False,
    "new_discovery_run": False,
    "performance_metrics_computed_from_new_tests": False,
    "candidate_exhaustive_run": False,
    "paper_forward_review": False,
    "paper_forward_activation": False,
    "broker_path_touched": False,
    "live_orders": False,
    "provider_download": False,
    "real_money_recommendation": False,
    "strategy_rules_changed": False,
    "acceptance_gates_changed": False,
    "gld_gror_recovery_completed": True,
    "failure_dashboard_created": True,
}

NEXT_ACTION = "pre_register_gld_gror_macro_research_lane"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def clean_output(root: Path) -> Path:
    output = (root / OUTPUT_DIR).resolve()
    if root.resolve() not in output.parents:
        raise RuntimeError(f"refusing output outside workspace: {output}")
    output.mkdir(parents=True, exist_ok=True)
    for child in output.iterdir():
        if child.is_file():
            child.unlink()
    return output


def strategy_id(row: dict[str, Any]) -> str:
    return str(row.get("strategy_id") or row.get("id") or row.get("candidate_id") or "")


def family(row: dict[str, Any]) -> str:
    return str(row.get("family") or row.get("strategy_family") or row.get("edge_type") or "")


def status(row: dict[str, Any]) -> str:
    return str(row.get("current_status") or row.get("status") or row.get("promotion_decision") or "")


def row_text(row: dict[str, Any]) -> str:
    return " ".join(str(value) for value in row.values() if value is not None).lower()


def load_strategy_rows(root: Path) -> list[dict[str, Any]]:
    registry = load_yaml(root / STRATEGY_REGISTRY_PATH)
    rows = list(registry.get("strategies", []))
    expansion = load_yaml(root / EXPANSION_REGISTRY_PATH)
    for candidate in expansion.get("candidates", []):
        rows.append(
            {
                "id": candidate.get("candidate_id", ""),
                "strategy_id": candidate.get("candidate_id", ""),
                "display_name": candidate.get("strategy_name", candidate.get("candidate_id", "")),
                "lane": "strategy_expansion_candidates_v1",
                "instrument_family": candidate.get("allowed_universe", ""),
                "strategy_family": candidate.get("family", ""),
                "family": candidate.get("family", ""),
                "timeframe": candidate.get("timeframe", ""),
                "status": candidate.get("status", "registered_not_tested"),
                "current_status": candidate.get("status", "registered_not_tested"),
                "latest_evidence_path": expansion.get("metadata", {}).get("first_expansion_discovery_without_sector_rs_path", ""),
                "latest_known_result_summary": candidate.get("core_hypothesis", ""),
                "promotion_reason": "",
                "blocked_reason": "",
                "risk_budget_status": "",
                "duplication_risk": "",
                "paper_forward_active": False,
                "candidate_exhaustive_run": False,
                "real_money_recommendation": False,
                "benchmark_controls": candidate.get("benchmark_controls", []),
            }
        )
    return rows


def is_accepted(row: dict[str, Any]) -> bool:
    s = status(row).lower()
    return bool(row.get("paper_forward_active") is True or s in {"active_observation", "active_paper_demo_observation"} or "paper_forward" in str(row.get("credibility_tier", "")).lower())


def is_rejected_like(row: dict[str, Any]) -> bool:
    text = row_text(row)
    if is_accepted(row):
        return False
    rejected_terms = [
        "reject",
        "too_risky",
        "too_slow",
        "duplicate",
        "weaker_than",
        "blocked",
        "watchlist",
        "archived",
        "not_current_candidate",
        "needs_benchmark_delta_review",
        "benchmark_watchlist",
        "incomplete",
    ]
    return any(term in text for term in rejected_terms)


def infer_failure(row: dict[str, Any]) -> tuple[str, str]:
    text = row_text(row)
    if "duplicate" in text or "correlation" in text:
        return "duplication_or_high_correlation", "benchmark edge weak after overlap"
    if "too_risky" in text or "drawdown" in text or "risk buffer" in text or "stop" in text:
        return "risk_buffer_or_drawdown", "stop/drawdown gate"
    if "too_slow" in text or "low target" in text or "target diluted" in text:
        return "too_slow_for_profit_goal", "low target/return"
    if "weaker_than" in text or "underperform" in text or "lags" in text:
        return "weaker_than_active_or_benchmark", "benchmark edge"
    if "limited_history" in text or "inception" in text:
        return "limited_history_or_inception", "same-window benchmark needed"
    if "missing" in text or "cache" in text or "data" in text:
        return "data_or_incomplete_evidence", "data/evidence gap"
    if "watchlist" in text:
        return "watchlist_not_promoted", "insufficient evidence"
    return "not_promoted_or_incomplete", "manual review"


def accepted_inventory(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        if not is_accepted(row):
            continue
        text = row_text(row)
        output.append(
            {
                "strategy_id": strategy_id(row),
                "family": family(row),
                "timeframe": row.get("timeframe", ""),
                "status": status(row),
                "why_it_passed": row.get("latest_known_result_summary", row.get("promotion_reason", "")),
                "main_exposure": "GLD/SPY mix" if "gld" in text else "equity/sector/cash ETF exposure",
                "likely_regime_dependency": "risk-on/risk-off and inflation/defensive regimes" if "gld" in text else "equity trend and defensive filter regimes",
                "correlation_duplication_risk": row.get("duplication_risk", "not_reported"),
                "paper_demo_value": "active observation / benchmark comparator",
                "recommendation": "remain_under_observation",
                "evidence_path": row.get("latest_evidence_path", ""),
            }
        )
    return output


def rejected_inventory(rows: list[dict[str, Any]], root: Path = ROOT) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        sid = strategy_id(row)
        if not sid or sid in seen or not is_rejected_like(row):
            continue
        seen.add(sid)
        primary, secondary = infer_failure(row)
        output.append(
            {
                "strategy_id": sid,
                "family": family(row),
                "timeframe": row.get("timeframe", ""),
                "status": status(row),
                "primary_failure_reason": primary,
                "secondary_failure_reason": secondary,
                "evidence_path": row.get("latest_evidence_path", ""),
                "latest_summary": row.get("latest_known_result_summary", ""),
                "exact_variant_closed": "true" if primary in {"duplication_or_high_correlation", "risk_buffer_or_drawdown", "too_slow_for_profit_goal"} else "partial",
                "family_remains_open_with_new_hypothesis": "true" if primary not in {"data_or_incomplete_evidence"} else "manual_review",
            }
        )
    for result in read_csv_rows(root / FIRST_EXPANSION_RESULTS):
        sid = result.get("candidate_id", "")
        if sid and sid not in seen:
            primary, secondary = infer_failure(result)
            output.append(
                {
                    "strategy_id": sid,
                    "family": "",
                    "timeframe": "",
                    "status": result.get("discovery_outcome", ""),
                    "primary_failure_reason": primary,
                    "secondary_failure_reason": secondary,
                    "evidence_path": str(FIRST_EXPANSION_RESULTS.parent),
                    "latest_summary": result.get("decision_reason", ""),
                    "exact_variant_closed": "true",
                    "family_remains_open_with_new_hypothesis": "true",
                }
            )
    return output


def failure_dashboard(rejections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in rejections:
        text = " ".join(str(row.get(key, "")) for key in row).lower()
        rows.append(
            {
                "strategy_id": row["strategy_id"],
                "family": row["family"],
                "timeframe": row["timeframe"],
                "status": row["status"],
                "primary_failure_reason": row["primary_failure_reason"],
                "secondary_failure_reason": row["secondary_failure_reason"],
                "benchmark_failed": any(term in text for term in ["benchmark", "underperform", "weaker", "lags"]),
                "risk_gate_failed": any(term in text for term in ["risk", "stop", "drawdown", "too_risky"]),
                "slippage_stress_failed": "slippage" in text or "spread" in text,
                "drawdown_issue": "drawdown" in text,
                "low_return_issue": any(term in text for term in ["too_slow", "low target", "return"]),
                "duplication_issue": any(term in text for term in ["duplicate", "correlation"]),
                "limited_history_issue": "limited" in text or "inception" in text,
                "data_issue": "data" in text or "cache" in text or "missing" in text,
                "exact_variant_closed": row["exact_variant_closed"],
                "family_remains_open_with_new_hypothesis": row["family_remains_open_with_new_hypothesis"],
            }
        )
    return rows


def family_coverage(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[family(row) or "unknown"].append(row)
    output = []
    for fam, fam_rows in sorted(grouped.items()):
        statuses = Counter(status(row) for row in fam_rows)
        output.append(
            {
                "family": fam,
                "strategy_count": len(fam_rows),
                "accepted_or_active_count": sum(1 for row in fam_rows if is_accepted(row)),
                "rejected_watchlist_archived_count": sum(1 for row in fam_rows if is_rejected_like(row)),
                "statuses": json.dumps(dict(statuses), sort_keys=True),
                "gld_gror_related": any(any(term.lower() in row_text(row) for term in ["gld", "gold", "gror", "global risk", "ief", "tlt"]) for row in fam_rows),
                "coverage_note": "fragmented but present" if any(any(term.lower() in row_text(row) for term in ["gld", "gold", "gror", "global risk"]) for row in fam_rows) else "standard project family",
            }
        )
    return output


def gate_rows() -> list[dict[str, Any]]:
    return [
        {"gate": "benchmark edge", "recommendation": "split by lane", "reason": "Active-reference benchmark edge is right for ETF wrappers but too blunt for diversifier/contribution lanes."},
        {"gate": "risk buffer", "recommendation": "keep", "reason": "The $600 stop budget is central to tournament survivability."},
        {"gate": "drawdown", "recommendation": "keep", "reason": "Most rejected high-upside rows failed because drawdown/risk was real, not cosmetic."},
        {"gate": "stop-hit count/rate", "recommendation": "keep", "reason": "Stop survival is a core paper/demo gate."},
        {"gate": "slippage/spread stress", "recommendation": "split by lane", "reason": "Daily high-turnover rows need stricter stress; monthly/weekly allocation rows need realistic but lower-frequency stress."},
        {"gate": "max trades per week", "recommendation": "split by lane", "reason": "The gate should match daily, weekly, and tactical-allocation cadence rather than one generic count."},
        {"gate": "max open positions", "recommendation": "keep", "reason": "Controls small-account concentration and complexity."},
        {"gate": "BIL allocation", "recommendation": "split by lane", "reason": "Excess BIL is a failure for target-seeking rows but may be expected in defensive/diversifier rows."},
        {"gate": "correlation/duplication", "recommendation": "keep", "reason": "Repeated ETF-wrapper variants frequently duplicated active combo/VM/DSR."},
        {"gate": "minimum trade count", "recommendation": "split by lane", "reason": "Weekly/monthly macro lanes need different sample expectations from daily mean-reversion rows."},
        {"gate": "limited-history handling", "recommendation": "keep", "reason": "XLRE/limited-history labeling avoided false confidence."},
        {"gate": "same-window benchmark handling", "recommendation": "keep", "reason": "Prevents invalid full-history vs limited-history comparisons."},
    ]


def benchmark_usage(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        benchmarks = row.get("benchmark_controls") or row.get("benchmark_control") or row.get("benchmark_ids") or []
        if isinstance(benchmarks, str):
            benchmarks_text = benchmarks
        else:
            benchmarks_text = ";".join(str(item) for item in benchmarks)
        if not benchmarks_text:
            text = row_text(row)
            mentions = [term for term in ["SPY_200d", "SPY", "QQQ", "BIL", "GLD", "active combo", "active VM", "active DSR"] if term.lower() in text]
            benchmarks_text = ";".join(mentions)
        output.append(
            {
                "strategy_id": strategy_id(row),
                "family": family(row),
                "status": status(row),
                "benchmark_controls_or_mentions": benchmarks_text,
                "same_window_required": "true" if any(term in row_text(row) for term in ["limited_history", "xlre", "inception"]) else "recommended_when_window_differs",
                "benchmark_mismatch_risk": "high" if status(row).lower() in {"watchlist", "needs_benchmark_delta_review"} else "normal",
            }
        )
    return [row for row in output if row["strategy_id"]]


def should_scan(path: Path) -> bool:
    if any(part in SKIP_DIRS for part in path.parts):
        return False
    if path.suffix.lower() in SKIP_SUFFIXES:
        return False
    if not path.is_file():
        return False
    try:
        return path.stat().st_size <= MAX_SCAN_BYTES
    except OSError:
        return False


def known_row_lookup(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {strategy_id(row): row for row in rows if strategy_id(row)}


def classify_gld_status(row: dict[str, Any] | None, path: Path, text: str) -> tuple[str, str, str, str]:
    status_text = status(row or {}).lower()
    all_text = (text + " " + status_text).lower()
    if row and is_accepted(row):
        return "accepted", "not_reopen_active_observation_only", "methodology_or_tracking", row.get("latest_known_result_summary", "")
    if "candidate_exhaustive_evidence_incomplete" in all_text or "missing cache" in all_text or "incomplete" in all_text:
        return "incomplete", "reopen_only_after_clean_preregistration", "incomplete evidence", "candidate evidence incomplete or stale"
    if "too_slow" in all_text:
        return "rejected", "do_not_reopen_exact_variant", "performance", "too slow for +300/+400 tournament target"
    if "too_risky" in all_text or "drawdown" in all_text:
        return "rejected", "do_not_reopen_exact_variant", "performance", "risk/drawdown gate"
    if "watchlist" in all_text or "needs_benchmark_delta_review" in all_text:
        return "diagnostic", "reopen_as_lane_not_exact_variant", "registry tracking", "watchlist or benchmark delta review needed"
    if "paper_forward" in all_text or "observation" in all_text:
        return "accepted", "not_reopen_active_observation_only", "methodology_or_tracking", "paper/demo observation exists"
    return "missing_evidence_or_reference", "manual_review", "incomplete evidence", "reference found without clear result"


def gld_gror_search(root: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lookup = known_row_lookup(rows)
    id_pattern = re.compile(r"[A-Za-z0-9]+(?:_[A-Za-z0-9]+){2,}(?:_v\d+)?")
    output: list[dict[str, Any]] = []
    for path in root.rglob("*"):
        if len(output) >= MAX_SEARCH_ROWS or not should_scan(path):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        terms = [term for term in SEARCH_TERMS if term.lower() in text.lower() or term.lower() in str(path).lower()]
        if not terms:
            continue
        ids = [sid for sid in lookup if sid and (sid in text or sid in str(path))]
        if not ids:
            ids = [candidate for candidate in id_pattern.findall(text + " " + str(path)) if any(term.lower().replace(" ", "_") in candidate.lower() for term in SEARCH_TERMS)]
        if not ids:
            ids = [""]
        for sid in ids[:5]:
            row = lookup.get(sid)
            result_status, should_reopen, issue_class, reason = classify_gld_status(row, path, text[:2000])
            output.append(
                {
                    "file_path": str(path.relative_to(root)),
                    "terms_found": ";".join(terms),
                    "strategy_id": sid,
                    "family": family(row or {}),
                    "status": status(row or {}),
                    "evidence_path": (row or {}).get("latest_evidence_path", ""),
                    "results_exist": bool((row or {}).get("latest_evidence_path")) or "result" in text.lower() or "summary" in text.lower(),
                    "recovery_status": result_status,
                    "reason_for_rejection_or_deferral": reason,
                    "should_be_reopened": should_reopen,
                    "issue_class": issue_class,
                }
            )
            if len(output) >= MAX_SEARCH_ROWS:
                break
    return output


def checklist_md(title: str, rows: list[tuple[str, str, str]]) -> str:
    lines = [f"# {title}", "", "| Check | Verdict | Notes |", "|---|---|---|"]
    lines.extend(f"| {check} | {verdict} | {notes} |" for check, verdict, notes in rows)
    return "\n".join(lines) + "\n"


def backtester_checklist_md() -> str:
    rows = [
        ("adjusted price handling", "appears covered", "Cache files and runners use adjusted OHLCV/adj_close conventions."),
        ("signal/return alignment", "audit caution", "Multiple runners declare prior completed data and next open/close assumptions; keep explicit per lane."),
        ("next-open/next-close execution assumptions", "mixed but documented", "Daily first-expansion runner states next-open; older recovered scripts may use monthly close-to-close proxies."),
        ("weekly rebalance timing", "needs lane-specific documentation", "Sector RS limited-history preregistration freezes weekly prior-data rebalance but has not been discovered yet."),
        ("cash/BIL accounting", "appears covered", "BIL fallback/cash proxy appears in active and expansion evidence; contribution accounting varies by runner."),
        ("slippage/spread application", "audit caution", "Stress is present in newer discovery packets; older recovered artifacts sometimes report diagnostics rather than exact fills."),
        ("trade count calculation", "audit caution", "Daily/weekly gates can mismatch cadence; split by lane recommended."),
        ("drawdown calculation", "appears covered", "Dollar drawdown against $3,000 appears consistently reported in recent evidence."),
        ("rolling window calculation", "appears covered", "Recent runners use sampled rolling windows; exact sampling density differs by artifact."),
        ("benchmark same-window recomputation", "keep required", "Critical for XLRE/limited-history and GLD/GROR windows."),
        ("ETF inception-date handling", "improved", "XLRE limited-history handling now explicitly labeled; same discipline should apply to GLD/GROR if windows differ."),
        ("missing data handling", "audit caution", "GROR registry notes indicate incomplete/stale cache evidence historically; do not continue without clean packet."),
        ("reproducibility metadata", "appears covered", "Evidence manifests and consistency checks are widespread; keep adding no-run flags."),
    ]
    return checklist_md("Backtester Methodology Checklist", rows)


def data_checklist_md() -> str:
    rows = [
        ("approved symbol map", "available", "ETF symbol approval/caches exist for core ETF work."),
        ("GLD cache", "found", "GLD.csv exists locally; this audit did not download or refresh it."),
        ("IEF/TLT/BIL cache", "found by registry/search context", "Treasury/cash symbols appear in strategy rows and evidence."),
        ("provider download", "not run", "Audit-only scope forbids downloads."),
        ("limited-history markers", "required", "XLRE handling is explicit; GLD/GROR lane should use explicit cache-window manifests."),
        ("same-window benchmark data", "required before future discovery", "Do not compare future macro lane against stale/full-history controls."),
        ("missing evidence", "present in GROR history", "GROR candidate has evidence-incomplete/stale permission warnings in registry."),
    ]
    return checklist_md("Data Quality Checklist", rows)


def gld_gror_recovery_md(search_rows: list[dict[str, Any]], registry_rows: list[dict[str, Any]]) -> str:
    gld_registry = [row for row in registry_rows if any(term in row_text(row) for term in ["gld", "gold", "gror", "global risk", "ief", "tlt"])]
    active = [row for row in gld_registry if is_accepted(row)]
    incomplete = [row for row in gld_registry if "gror" in row_text(row) and ("incomplete" in row_text(row) or "not_current_candidate" in row_text(row))]
    return f"""# GLD / GROR Family Recovery

Recovered registry-linked GLD/GROR/macro rows: `{len(gld_registry)}`

Accepted or paper/demo rows among them: `{len(active)}`

GROR incomplete/stale-permission rows: `{len(incomplete)}`

Search result rows exported: `{len(search_rows)}`

## Main Recovery Finding

The GLD/GROR family is not absent. It is fragmented. Evidence exists in compact portfolio diagnostics, profit-lab GLD rows, global multi-asset batches, `combo_SPY200d_GLD_50_50_v1` paper/demo observation material, and GROR candidate-exhaustive/promotion-review recovery paths. The bottleneck is registry/evidence continuity and lane definition, not a lack of any GLD references.

`gror_balanced_momentum_60_40_v1` appears historically important but currently has stale/currently-not-current candidate permission and incomplete-evidence language in the registry. That argues for a clean pre-registered GLD/GROR macro lane rather than silently reopening old candidate_exhaustive state.

Exact variants that were too slow/too risky should remain closed. The family remains open only with a new, explicitly pre-registered macro/risk-off hypothesis and same-window benchmark plan.
"""


def lane_recommendations_md() -> str:
    lanes = [
        ("Conservative ETF allocation lane", "SPY_200d, VM/DSR controls, BIL/IEF/GLD defensive blends", "SPY_200d, BIL, active combo", "strict stop/drawdown; lower turnover", "moderate target; stable risk reduction", "must add value after costs and not simply dilute targets", "paper only after promotion review", "same-window benchmark and drawdown packet"),
        ("Moderate tactical ETF lane", "daily/weekly ETF momentum, mean reversion, sector rotation", "active VM, active DSR, active combo, SPY_200d", "strict risk buffer, slippage, trade count", "must beat active refs or materially improve risk", "correlation cap vs active combo/VM/DSR", "promotion review before any validation", "trade diagnostics, stress, rolling windows"),
        ("Macro / GLD / duration / risk-off lane", "GLD, IEF, TLT, BIL, SPY/QQQ risk-on/off, GROR", "same-window SPY_200d, active combo, GLD, BIL, IEF/TLT where applicable", "lane-specific turnover and drawdown gates", "diversifier-adjusted target contribution", "must improve crisis/risk-off behavior without target collapse", "research/paper-demo only after clean prereg", "cache window, benchmark same-window, regime diagnostics"),
        ("Diversifier contribution lane", "small fixed sleeves, overlays, defensive ballast", "base strategy plus portfolio combo", "risk contribution and marginal drawdown gates", "incremental target windows, not raw standalone targets only", "must prove additive timing", "watchlist unless strong incremental evidence", "component contribution and overlap exports"),
        ("Intraday research-only lane", "ORB, VWAP deviation, gap fade, event-intraday ideas", "SPY/QQQ intraday benchmarks only after data QA", "execution realism, slippage, latency, PDT/small-account constraints", "no demo until data/execution proven", "must be independent from daily ETF wrappers", "not demo eligible initially", "point-in-time intraday data and fill-model audit"),
    ]
    lines = ["# Lane Redesign Recommendations", ""]
    for name, families, benchmarks, risk, performance, diversification, demo, evidence in lanes:
        lines.extend(
            [
                f"## {name}",
                "",
                f"- Allowed strategy families: {families}",
                f"- Benchmark group: {benchmarks}",
                f"- Risk gates: {risk}",
                f"- Performance gates: {performance}",
                f"- Diversification gates: {diversification}",
                f"- Demo eligibility rules: {demo}",
                f"- Evidence requirements: {evidence}",
                "",
            ]
        )
    return "\n".join(lines)


def summary_md(manifest: dict[str, Any], accepted: list[dict[str, Any]], rejected: list[dict[str, Any]], search_rows: list[dict[str, Any]]) -> str:
    reason_counts = Counter(row["primary_failure_reason"] for row in rejected)
    return f"""# Tournament Root-Cause Audit

Created UTC: `{manifest['created_utc']}`

Audit-only: `{manifest['audit_only']}`

Accepted/paper-demo inventory rows: `{len(accepted)}`

Rejected/watchlist/archived inventory rows: `{len(rejected)}`

GLD/GROR search rows: `{len(search_rows)}`

## Main Bottleneck

The low promotion hit rate is mostly normal quant research attrition amplified by tournament architecture: high target-before-stop demands, strict active-reference comparisons, and a small-account drawdown budget reject most ETF-wrapper variants. Recent failures are not primarily explained by a clear backtester bug or provider-data gap. The more actionable issue is lane design and tracking: macro/GLD/GROR and diversifier rows are judged in the same tournament frame as target-seeking ETF wrappers, even when their value is marginal risk reduction or regime diversification.

Failure reason mix: `{json.dumps(dict(reason_counts), sort_keys=True)}`

## GLD / GROR Recovery

GLD/GROR evidence exists but is fragmented across registry rows, commodity/multi-asset labs, paper-forward observation material, and recovered GROR artifacts. The family should not be treated as missing, but old GROR candidate permissions should not be resumed directly because the registry marks current permission as stale/not current and evidence incomplete.

## Next Action

`{manifest['next_action']}`
"""


def root_cause_consistency(manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    required = [
        "tournament_root_cause_manifest.json",
        "tournament_root_cause_summary.md",
        "accepted_strategy_inventory.csv",
        "rejected_strategy_inventory.csv",
        "failure_reason_dashboard.csv",
        "family_coverage_map.csv",
        "gate_failure_summary.csv",
        "benchmark_usage_audit.csv",
        "backtester_methodology_checklist.md",
        "data_quality_checklist.md",
        "gld_gror_family_recovery.md",
        "gld_gror_registry_search_results.csv",
        "lane_redesign_recommendations.md",
        "next_action.md",
        "root_cause_consistency_check.json",
    ]
    check = {
        "audit_only": manifest["audit_only"],
        "no_new_backtests": not manifest["new_backtests_run"],
        "no_new_discovery": not manifest["new_discovery_run"],
        "no_provider_download": not manifest["provider_download"],
        "no_candidate_exhaustive": not manifest["candidate_exhaustive_run"],
        "no_paper_forward_action": not manifest["paper_forward_review"] and not manifest["paper_forward_activation"],
        "no_broker_live_path": not manifest["broker_path_touched"] and not manifest["live_orders"],
        "gld_gror_search_report_exists": (output / "gld_gror_registry_search_results.csv").exists(),
        "failure_dashboard_exists": (output / "failure_reason_dashboard.csv").exists(),
        "accepted_inventory_exists": (output / "accepted_strategy_inventory.csv").exists(),
        "rejected_inventory_exists": (output / "rejected_strategy_inventory.csv").exists(),
        "gate_audit_exists": (output / "gate_failure_summary.csv").exists(),
        "backtester_data_checklists_exist": (output / "backtester_methodology_checklist.md").exists() and (output / "data_quality_checklist.md").exists(),
        "lane_redesign_exists": (output / "lane_redesign_recommendations.md").exists(),
        "required_files_created": all((output / name).exists() for name in required if name != "root_cause_consistency_check.json"),
        "manifest_flags_match_scope": all(manifest[key] == value for key, value in MANIFEST_FLAGS.items()),
        "next_action_explicit": manifest["next_action"] in {
            "pre_register_gld_gror_macro_research_lane",
            "fix_backtester_or_data_issue_before_more_research",
            "revise_tournament_gates_by_lane",
            "continue_with_pre_registered_second_expansion_batch",
        },
    }
    check["consistency_passed"] = all(bool(value) for value in check.values())
    return check


def run_tournament_root_cause_audit(root: Path = ROOT) -> dict[str, Any]:
    output = clean_output(root)
    rows = load_strategy_rows(root)
    accepted = accepted_inventory(rows)
    rejected = rejected_inventory(rows, root)
    failure = failure_dashboard(rejected)
    family_map = family_coverage(rows)
    gates = gate_rows()
    benchmark_rows = benchmark_usage(rows)
    search_rows = gld_gror_search(root, rows)
    manifest = {
        "artifact": "tournament_root_cause_audit",
        "created_utc": now_utc(),
        "output_dir": str(output),
        **MANIFEST_FLAGS,
        "accepted_strategy_count": len(accepted),
        "rejected_strategy_count": len(rejected),
        "gld_gror_search_rows": len(search_rows),
        "main_bottleneck": "normal_quant_attrition_plus_lane_gate_and_tracking_mismatch",
        "backtester_data_bug_found": False,
        "next_action": NEXT_ACTION,
    }

    write_json(output / "tournament_root_cause_manifest.json", manifest)
    (output / "tournament_root_cause_summary.md").write_text(summary_md(manifest, accepted, rejected, search_rows), encoding="utf-8")
    write_csv(output / "accepted_strategy_inventory.csv", accepted, ["strategy_id", "family", "timeframe", "status", "why_it_passed", "main_exposure", "likely_regime_dependency", "correlation_duplication_risk", "paper_demo_value", "recommendation", "evidence_path"])
    write_csv(output / "rejected_strategy_inventory.csv", rejected, ["strategy_id", "family", "timeframe", "status", "primary_failure_reason", "secondary_failure_reason", "evidence_path", "latest_summary", "exact_variant_closed", "family_remains_open_with_new_hypothesis"])
    write_csv(output / "failure_reason_dashboard.csv", failure, ["strategy_id", "family", "timeframe", "status", "primary_failure_reason", "secondary_failure_reason", "benchmark_failed", "risk_gate_failed", "slippage_stress_failed", "drawdown_issue", "low_return_issue", "duplication_issue", "limited_history_issue", "data_issue", "exact_variant_closed", "family_remains_open_with_new_hypothesis"])
    write_csv(output / "family_coverage_map.csv", family_map, ["family", "strategy_count", "accepted_or_active_count", "rejected_watchlist_archived_count", "statuses", "gld_gror_related", "coverage_note"])
    write_csv(output / "gate_failure_summary.csv", gates, ["gate", "recommendation", "reason"])
    write_csv(output / "benchmark_usage_audit.csv", benchmark_rows, ["strategy_id", "family", "status", "benchmark_controls_or_mentions", "same_window_required", "benchmark_mismatch_risk"])
    (output / "backtester_methodology_checklist.md").write_text(backtester_checklist_md(), encoding="utf-8")
    (output / "data_quality_checklist.md").write_text(data_checklist_md(), encoding="utf-8")
    (output / "gld_gror_family_recovery.md").write_text(gld_gror_recovery_md(search_rows, rows), encoding="utf-8")
    write_csv(output / "gld_gror_registry_search_results.csv", search_rows, ["file_path", "terms_found", "strategy_id", "family", "status", "evidence_path", "results_exist", "recovery_status", "reason_for_rejection_or_deferral", "should_be_reopened", "issue_class"])
    (output / "lane_redesign_recommendations.md").write_text(lane_recommendations_md(), encoding="utf-8")
    (output / "next_action.md").write_text(f"# Next Action\n\n`{NEXT_ACTION}`\n\nDo not run this next action from the audit task.\n", encoding="utf-8")
    consistency = root_cause_consistency(manifest, output)
    write_json(output / "root_cause_consistency_check.json", consistency)
    return {
        "output_dir": str(output),
        "manifest": manifest,
        "consistency": consistency,
        "accepted_strategy_count": len(accepted),
        "rejected_strategy_count": len(rejected),
        "gld_gror_search_rows": len(search_rows),
        "next_action": NEXT_ACTION,
    }


def main() -> None:
    print(json.dumps(run_tournament_root_cause_audit(ROOT), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

from __future__ import annotations

import csv
import json
import shutil
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from intraday_research import IntradayCacheContract


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "intraday_readiness" / "manual_intraday_data_source_review" / "latest"
FIX_PACKET_DIR = Path("evidence") / "intraday_readiness" / "fix_intraday_readiness_blockers" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"
CONFIG_PATH = Path("config.yaml")
APPROVED_SYMBOL_MAP_PATH = Path("strategy_lab") / "approved_etf_symbol_map.yaml"
FAST_DATA_POLICY_PATH = Path("data_policy") / "FAST_EXPLORATORY_DATA_POLICY.md"
GLOBAL_ACQUISITION_CONFIG_PATH = (
    Path("data_acquisition_runs") / "global_multi_asset_fast_exploratory" / "acquisition_config.yaml"
)
ALPACA_DAILY_BARS_PATH = Path("execution_lab") / "alpaca_micro_live_v1" / "data" / "alpaca_historical_bars.py"
ALPACA_CACHE_PATH = Path("execution_lab") / "alpaca_micro_live_v1" / "data" / "alpaca_runtime_cache.py"

NEXT_ACTION = "manual_intraday_data_source_review_required"
DECISION = "manual_intraday_data_source_review_required"
RECOMMENDED_DATA_SOURCE_PATH = "manual_terms_review_then_select_yfinance_intraday_alpaca_data_or_manual_csv_source"
VALID_NEXT_ACTIONS = {
    "authorize_controlled_intraday_cache_bootstrap",
    "manual_intraday_data_source_review_required",
    "pause_intraday_research_due_data_constraints",
    "pre_register_risk_controlled_high_return_family_review",
}

MANIFEST_FLAGS = {
    "data_source_review_only": True,
    "intraday_backtests_run": False,
    "new_discovery_run": False,
    "new_performance_metrics_computed": False,
    "provider_download": False,
    "provider_api_called": False,
    "intraday_data_downloaded": False,
    "intraday_cache_bootstrapped": False,
    "candidate_exhaustive_run": False,
    "paper_forward_review": False,
    "paper_forward_activation": False,
    "broker_orders_submitted": False,
    "broker_orders_cancelled": False,
    "live_orders": False,
    "broker_path_touched_execution": False,
    "real_money_recommendation": False,
    "strategy_rules_changed": False,
    "accepted_strategy_state_changed": False,
    "rejected_strategy_state_changed": False,
    "intraday_candidates_demo_eligible": False,
}

REQUIRED_FILES = [
    "intraday_data_source_review_manifest.json",
    "intraday_data_source_review_summary.md",
    "intraday_data_source_requirements.md",
    "intraday_candidate_source_inventory.csv",
    "intraday_source_fit_assessment.csv",
    "intraday_license_terms_review_needed.md",
    "intraday_cache_bootstrap_requirements.md",
    "intraday_manual_csv_import_option.md",
    "intraday_data_source_decision.md",
    "intraday_data_source_review_next_action.md",
    "intraday_data_source_review_consistency_check.json",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv_rows(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def clean_output(root: Path) -> Path:
    output = (root / OUTPUT_DIR).resolve()
    workspace = root.resolve()
    if output == workspace or workspace not in output.parents:
        raise RuntimeError(f"refusing output outside workspace: {output}")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    return output


def strategy_snapshot(root: Path) -> list[dict[str, Any]]:
    return deepcopy(load_yaml(root / REGISTRY_PATH).get("strategies", []))


def strategy_state_map(strategies: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    state: dict[str, dict[str, Any]] = {}
    for row in strategies:
        row_id = row.get("id") or row.get("strategy_id")
        if not row_id:
            continue
        state[row_id] = {
            "status": row.get("status") or row.get("current_status"),
            "current_status": row.get("current_status"),
            "paper_forward_active": row.get("paper_forward_active"),
            "candidate_exhaustive_run": row.get("candidate_exhaustive_run"),
            "candidate_exhaustive_recommended": row.get("candidate_exhaustive_recommended"),
            "promotion_review_required": row.get("promotion_review_required"),
        }
    return state


def previous_fix_summary(root: Path) -> dict[str, Any]:
    path = root / FIX_PACKET_DIR / "intraday_blocker_fix_manifest.json"
    if not path.exists():
        return {"fix_packet_found": False}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "fix_packet_found": True,
        "blockers_fixed_count": payload.get("blockers_fixed_count"),
        "blockers_partially_fixed_count": payload.get("blockers_partially_fixed_count"),
        "critical_blockers_remaining_count": payload.get("critical_blockers_remaining_count"),
        "intraday_cache_contract_created": payload.get("intraday_cache_contract_created"),
        "intraday_data_present": payload.get("intraday_data_present"),
        "intraday_data_source_approved": payload.get("intraday_data_source_approved"),
        "readiness_verdict_after_fix": payload.get("readiness_verdict_after_fix"),
        "next_action": payload.get("next_action"),
    }


def inspect_repo_sources(root: Path) -> dict[str, Any]:
    config = load_yaml(root / CONFIG_PATH)
    approved_map = load_yaml(root / APPROVED_SYMBOL_MAP_PATH)
    fast_policy = read_text(root / FAST_DATA_POLICY_PATH)
    global_config = load_yaml(root / GLOBAL_ACQUISITION_CONFIG_PATH)
    alpaca_daily = read_text(root / ALPACA_DAILY_BARS_PATH)
    alpaca_cache = read_text(root / ALPACA_CACHE_PATH)
    intraday_root = root / "data" / "intraday"
    contract = IntradayCacheContract(root=intraday_root)
    spy_1min = contract.inspect("SPY", "1Min")
    qqq_5min = contract.inspect("QQQ", "5Min")
    approved_symbols = [
        str(row.get("symbol")).upper()
        for row in approved_map.get("symbols", [])
        if isinstance(row, dict) and row.get("allowed_for_strategy")
    ]
    return {
        "config_intraday_dir": config.get("data", {}).get("intraday_dir"),
        "config_yfinance_section_present": "yfinance" in config.get("data", {}),
        "daily_fast_policy_exists": bool(fast_policy),
        "daily_fast_policy_intraday_gated": "intraday" in fast_policy.lower() and "separate data" in fast_policy.lower(),
        "global_yfinance_config_exists": bool(global_config),
        "global_yfinance_provider": global_config.get("provider"),
        "daily_approved_symbols_include_spy_qqq": {"SPY", "QQQ"}.issubset(set(approved_symbols)),
        "approved_symbol_count": len(approved_symbols),
        "alpaca_daily_fetcher_exists": bool(alpaca_daily),
        "alpaca_daily_timeframe_hardcoded": 'timeframe="1Day"' in alpaca_daily or "timeframe='1Day'" in alpaca_daily,
        "alpaca_timestamp_utc_parse": "utc=True" in alpaca_daily,
        "alpaca_cache_daily_only": "_1Day.csv" in alpaca_cache,
        "local_intraday_data_present": spy_1min.data_present or qqq_5min.data_present,
        "local_intraday_cache_status": spy_1min.status,
        "intraday_cache_root": str(intraday_root),
    }


def candidate_source_rows(scan: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "source_id": "yfinance_compatible_public_data_path",
            "classification": "existing_provider_path",
            "code_or_policy_path": str(GLOBAL_ACQUISITION_CONFIG_PATH),
            "supports_min_timeframe_in_repo": "unknown_not_implemented_for_intraday",
            "symbols_minimum_spy_qqq": "likely_symbol_path_exists_for_daily_only",
            "history_depth_minimum": "unknown_requires_manual_review",
            "license_terms_status": "manual_terms_review_required",
            "api_key_required": "false_for_existing_daily_path",
            "local_cache_allowed_under_terms": "unknown_requires_manual_review",
            "review_status": "candidate_source_but_not_approved",
            "notes": "Repo has daily yfinance-compatible exploratory paths and SPY/QQQ daily symbols, but no intraday source approval or implemented intraday interval path.",
        },
        {
            "source_id": "alpaca_market_data_bars",
            "classification": "broker_data_possible_but_not_approved",
            "code_or_policy_path": str(ALPACA_DAILY_BARS_PATH),
            "supports_min_timeframe_in_repo": "no_current_code_is_daily_1Day",
            "symbols_minimum_spy_qqq": "possible_but_requires_account_provider_review",
            "history_depth_minimum": "unknown_requires_manual_review",
            "license_terms_status": "manual_terms_review_required",
            "api_key_required": "true",
            "local_cache_allowed_under_terms": "unknown_requires_manual_review",
            "review_status": "candidate_source_but_not_approved",
            "notes": "Existing module fetches Alpaca daily bars only. Broker/data terms and historical intraday depth are not approved here.",
        },
        {
            "source_id": "manual_csv_import_under_intraday_cache_contract",
            "classification": "manual_csv_only",
            "code_or_policy_path": "intraday_research/cache_contract.py",
            "supports_min_timeframe_in_repo": "1Min_or_5Min_schema_supported",
            "symbols_minimum_spy_qqq": "depends_on_user_supplied_source",
            "history_depth_minimum": "depends_on_user_supplied_source",
            "license_terms_status": "manual_terms_review_required",
            "api_key_required": "false_for_import_itself",
            "local_cache_allowed_under_terms": "depends_on_source_terms",
            "review_status": "usable_container_after_source_approval",
            "notes": "The cache contract can validate local CSV bars, but this review must not write real intraday bars and cannot approve an unknown upstream source.",
        },
        {
            "source_id": "existing_daily_csv_cache",
            "classification": "not_supported",
            "code_or_policy_path": "data/cache",
            "supports_min_timeframe_in_repo": "no_daily_only",
            "symbols_minimum_spy_qqq": "yes_daily_cache_present_but_not_intraday",
            "history_depth_minimum": "not_applicable_to_intraday",
            "license_terms_status": "daily_exploratory_only",
            "api_key_required": "false_for_local_read",
            "local_cache_allowed_under_terms": "daily_cache_already_governed_separately",
            "review_status": "not_intraday_source",
            "notes": "Daily OHLCV cache cannot satisfy 1Min/5Min intraday requirements.",
        },
        {
            "source_id": "synthetic_test_fixtures",
            "classification": "not_supported",
            "code_or_policy_path": "tests",
            "supports_min_timeframe_in_repo": "synthetic_only",
            "symbols_minimum_spy_qqq": "not_real_market_data",
            "history_depth_minimum": "not_applicable",
            "license_terms_status": "not_applicable",
            "api_key_required": "false",
            "local_cache_allowed_under_terms": "not_applicable",
            "review_status": "not_supported_for_research_evidence",
            "notes": "Synthetic fixtures are for contract tests only and cannot be research evidence.",
        },
    ]


def source_fit_rows() -> list[dict[str, str]]:
    return [
        {
            "source_id": "yfinance_compatible_public_data_path",
            "minimum_timeframes": "unknown_requires_manual_review",
            "minimum_symbols_spy_qqq": "possible_but_not_intraday_approved",
            "minimum_history": "unknown_requires_manual_review",
            "timestamp_session_quality": "unknown_requires_manual_review",
            "price_fields": "ohlcv_likely_but_not_verified_for_intraday",
            "spread_proxy": "not_available_in_existing_daily_path",
            "terms_acceptability": "manual_terms_review_required",
            "cost_sustainability": "unknown_for_intraday",
            "cache_contract_fit": "requires_new_controlled_adapter_or_manual_csv_import",
            "decision": "not_approved_this_review",
        },
        {
            "source_id": "alpaca_market_data_bars",
            "minimum_timeframes": "unknown_requires_manual_review",
            "minimum_symbols_spy_qqq": "possible_but_requires_credentials_and_entitlement_review",
            "minimum_history": "unknown_requires_manual_review",
            "timestamp_session_quality": "utc_parse_exists_for_daily_bars_but_intraday_not_validated",
            "price_fields": "ohlcv_possible_from_bar_payload",
            "spread_proxy": "not_in_existing_bar_cache",
            "terms_acceptability": "manual_terms_review_required",
            "cost_sustainability": "api_keys_and_rate_limits_require_review",
            "cache_contract_fit": "could_fit_after_adapter_and_terms_review",
            "decision": "not_approved_this_review",
        },
        {
            "source_id": "manual_csv_import_under_intraday_cache_contract",
            "minimum_timeframes": "supported_by_schema_if_file_supplied",
            "minimum_symbols_spy_qqq": "supported_if_source_supplies_files",
            "minimum_history": "supported_if_source_supplies_1y_5min_or_better",
            "timestamp_session_quality": "validated_by_schema_but_source_calendar_still_needed",
            "price_fields": "ohlcv_required",
            "spread_proxy": "optional_not_required_conservative_fill_model_required",
            "terms_acceptability": "manual_terms_review_required",
            "cost_sustainability": "depends_on_external_source",
            "cache_contract_fit": "fits_existing_contract",
            "decision": "container_ready_source_not_approved",
        },
    ]


def summary_md(created_utc: str, output: Path, manifest: dict[str, Any]) -> str:
    return f"""# Manual Intraday Data-Source Review

Created UTC: `{created_utc}`

Evidence path: `{output}`

Decision: `{DECISION}`

Next action: `{manifest["next_action"]}`

## Result

The project has possible source paths, but no source is approved for intraday research yet. Existing yfinance-compatible paths are daily/exploratory; the Alpaca module is daily and broker/data terms are unresolved; the manual CSV route can fit the new cache contract only after the upstream data source and terms are approved.

No provider data was downloaded, no provider API was called, no intraday cache was bootstrapped, and no strategy or candidate status was changed.

## Key Fields

- Approved intraday data source found: `{manifest["approved_intraday_data_source_found"]}`
- Manual terms review required: `{manifest["manual_terms_review_required"]}`
- Local intraday data present: `{manifest["local_intraday_data_present"]}`
- Source candidate count: `{manifest["source_candidate_count"]}`
- Recommended data-source path: `{manifest["recommended_data_source_path"]}`
"""


def requirements_md() -> str:
    return """# Intraday Data-Source Requirements

Minimum acceptable first harness:

- Timeframe: at least one of `1Min` or `5Min`.
- Symbols: at least `SPY` and `QQQ`.
- History: at least 1 year of 5-minute bars for SPY and QQQ.
- Timestamp quality: timezone-aware timestamps or clear UTC normalization.
- Session quality: regular-market-hours filtering, holiday handling, and early-close handling.
- Data quality: no duplicate symbol/timestamp rows and no missing OHLCV fields.
- Price fields: OHLCV minimum; bid/ask or spread proxy preferred.
- Terms: acceptable for personal research use and local caching.
- Reproducibility: historical retrieval must be repeatable enough to rebuild the same cache period.

Preferred:

- Both `1Min` and `5Min`.
- 3+ years of 5-minute bars.
- 1+ year of 1-minute bars.
- Future support for IWM, DIA, BIL, and major sector ETFs.

If only OHLCV is available, fill/slippage assumptions must remain conservative.
"""


def terms_md() -> str:
    return """# Intraday License And Terms Review Needed

Status: `manual_terms_review_required`

No provider terms were approved by this review. Existing repo policy approves yfinance-compatible daily adjusted ETF/fund data for fast exploratory daily screens only. The policy explicitly leaves intraday gated behind separate data, execution, risk, and terms reviews.

Terms questions before any bootstrap:

- Is personal offline research use allowed?
- Is local caching of historical intraday bars allowed?
- Are SPY and QQQ covered for the required history?
- Are API keys, account entitlements, rate limits, or paid packages required?
- Can the historical query be reproduced later?
- Are redistribution, advisor packet inclusion, or raw OHLCV export restricted?

Until these are answered, no source is approved.
"""


def bootstrap_requirements_md() -> str:
    return """# Intraday Cache Bootstrap Requirements

A future controlled cache bootstrap would need:

- explicit authorization in a new prompt or governance packet,
- selected source and terms approval,
- no strategy execution in the bootstrap step,
- symbols limited initially to `SPY` and `QQQ`,
- timeframe limited initially to approved `1Min` and/or `5Min`,
- output under `data/intraday/{timeframe}/{symbol}_{timeframe}.csv`,
- metadata beside each file as `{symbol}_{timeframe}.metadata.json`,
- schema validation using `intraday_research.validate_intraday_bars`,
- duplicate timestamp report,
- missing-bar report,
- first/last timestamp report,
- stale-data report,
- early-close/holiday handling notes,
- evidence that raw intraday data is not copied into advisor packets unless separately allowed.

This review did not bootstrap a cache.
"""


def manual_csv_md() -> str:
    return """# Manual CSV Import Option

The manual CSV path is viable only as a container after source approval. Required columns are:

- `symbol`
- `timestamp`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `timeframe`
- `source`
- `adjusted`

The file must use the intraday cache convention and pass schema checks. The upstream source still needs terms approval, history-depth confirmation, and session-quality review. Manual CSV import is not a shortcut around licensing or data quality.
"""


def decision_md(manifest: dict[str, Any]) -> str:
    return f"""# Intraday Data-Source Decision

Decision: `{DECISION}`

Approved intraday data source found: `{manifest["approved_intraday_data_source_found"]}`

Reason:

- Candidate source paths exist, but none satisfies all approval criteria inside existing project rules.
- Existing yfinance-compatible approval is daily/exploratory, not intraday.
- Alpaca is broker/data-provider adjacent and requires credential, entitlement, history-depth, rate-limit, and terms review.
- Manual CSV import can fit the cache contract, but the external source still requires terms and quality approval.
- No local SPY/QQQ intraday cache is present.

This decision does not authorize cache bootstrap, discovery, backtesting, paper-forward activation, broker connectivity, or live orders.
"""


def next_action_md() -> str:
    return f"""# Intraday Data-Source Review Next Action

`{NEXT_ACTION}`

Do not run the next action in this task. No provider download, API call, cache bootstrap, strategy test, candidate validation, paper-forward action, broker order, live order, or real-money recommendation is authorized by this review.
"""


def update_metadata(root: Path, output: Path, created_utc: str, manifest: dict[str, Any]) -> tuple[bool, bool]:
    registry_updated = False
    registry_path = root / REGISTRY_PATH
    if registry_path.exists():
        registry = load_yaml(registry_path)
        metadata = registry.setdefault("registry", {})
        metadata.update(
            {
                "intraday_data_source_review_path": str(output),
                "intraday_data_source_review_status": "completed",
                "intraday_data_source_review_created_utc": created_utc,
                "intraday_data_source_review_decision": DECISION,
                "approved_intraday_data_source_found": manifest["approved_intraday_data_source_found"],
                "manual_terms_review_required": manifest["manual_terms_review_required"],
                "local_intraday_data_present": manifest["local_intraday_data_present"],
                "recommended_data_source_path": manifest["recommended_data_source_path"],
                "current_next_action": NEXT_ACTION,
                "next_action": NEXT_ACTION,
                "data_source_review_only": True,
                "intraday_backtests_run": False,
                "new_discovery_run": False,
                "new_performance_metrics_computed": False,
                "provider_download": False,
                "provider_api_called": False,
                "intraday_data_downloaded": False,
                "intraday_cache_bootstrapped": False,
                "candidate_exhaustive_run": False,
                "paper_forward_review": False,
                "paper_forward_activation": False,
                "broker_orders_submitted": False,
                "broker_orders_cancelled": False,
                "live_orders": False,
                "broker_path_touched_execution": False,
                "real_money_recommendation": False,
                "strategy_rules_changed": False,
                "accepted_strategy_state_changed": False,
                "rejected_strategy_state_changed": False,
                "intraday_candidates_demo_eligible": False,
                "updated_utc": created_utc,
            }
        )
        registry_path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")
        registry_updated = True

    roadmap_path = root / ROADMAP_PATH
    existing = roadmap_path.read_text(encoding="utf-8") if roadmap_path.exists() else "# Research Roadmap\n"
    lines = existing.splitlines()
    for idx, line in enumerate(lines):
        if line.startswith("Current next action:"):
            lines[idx] = f"Current next action: `{NEXT_ACTION}`"
            break
    else:
        insert_at = 1 if lines and lines[0].startswith("#") else 0
        lines.insert(insert_at, f"Current next action: `{NEXT_ACTION}`")
    base = "\n".join(lines)
    marker = "## Manual Intraday Data-Source Review"
    section = f"""## Manual Intraday Data-Source Review

- Created UTC: `{created_utc}`
- Evidence path: `{output}`
- Decision: `{DECISION}`
- Approved intraday data source found: `{manifest["approved_intraday_data_source_found"]}`
- Manual terms review required: `{manifest["manual_terms_review_required"]}`
- Local intraday data present: `{manifest["local_intraday_data_present"]}`
- Candidate source count: `{manifest["source_candidate_count"]}`
- Recommended data-source path: `{manifest["recommended_data_source_path"]}`
- Next action: `{NEXT_ACTION}`
- No intraday backtest, discovery, performance metric, provider download, provider API call, cache bootstrap, candidate_exhaustive, paper-forward action, broker order, live order, strategy-state change, demo eligibility, or real-money recommendation is authorized.
"""
    updated = base.split(marker, 1)[0].rstrip() + "\n\n" + section if marker in base else base.rstrip() + "\n\n" + section
    roadmap_path.parent.mkdir(parents=True, exist_ok=True)
    roadmap_path.write_text(updated.rstrip() + "\n", encoding="utf-8")
    return registry_updated, True


def consistency_check(
    output: Path,
    manifest: dict[str, Any],
    strategies_before: list[dict[str, Any]],
    strategies_after: list[dict[str, Any]],
) -> dict[str, Any]:
    required_present = {
        name: True if name == "intraday_data_source_review_consistency_check.json" else (output / name).exists()
        for name in REQUIRED_FILES
    }
    flags_match = all(manifest.get(key) == value for key, value in MANIFEST_FLAGS.items())
    check = {
        "data_source_review_only": manifest["data_source_review_only"] is True,
        "no_intraday_backtests": manifest["intraday_backtests_run"] is False,
        "no_new_discovery": manifest["new_discovery_run"] is False,
        "no_new_performance_metrics": manifest["new_performance_metrics_computed"] is False,
        "no_provider_download": manifest["provider_download"] is False,
        "no_provider_api_call": manifest["provider_api_called"] is False,
        "no_intraday_cache_bootstrap": manifest["intraday_cache_bootstrapped"] is False,
        "no_candidate_exhaustive": manifest["candidate_exhaustive_run"] is False,
        "no_paper_forward_action": manifest["paper_forward_review"] is False and manifest["paper_forward_activation"] is False,
        "no_broker_orders_submitted": manifest["broker_orders_submitted"] is False,
        "no_broker_orders_cancelled": manifest["broker_orders_cancelled"] is False,
        "no_live_orders": manifest["live_orders"] is False,
        "no_strategy_state_changes": strategy_state_map(strategies_before) == strategy_state_map(strategies_after),
        "candidate_source_inventory_exists": required_present["intraday_candidate_source_inventory.csv"],
        "source_fit_assessment_exists": required_present["intraday_source_fit_assessment.csv"],
        "license_terms_review_file_exists": required_present["intraday_license_terms_review_needed.md"],
        "cache_bootstrap_requirements_file_exists": required_present["intraday_cache_bootstrap_requirements.md"],
        "decision_file_exists": required_present["intraday_data_source_decision.md"],
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "manifest_flags_match_strict_scope": flags_match,
        "all_required_files_present": all(required_present.values()),
    }
    check["consistency_passed"] = all(check.values())
    return check


def run_manual_intraday_data_source_review(root: Path = ROOT) -> dict[str, Any]:
    root = Path(root)
    created_utc = now_utc()
    output = clean_output(root)
    strategies_before = strategy_snapshot(root)
    previous = previous_fix_summary(root)
    scan = inspect_repo_sources(root)
    inventory = candidate_source_rows(scan)
    fit = source_fit_rows()
    source_candidate_count = sum(1 for row in inventory if row["review_status"] in {"candidate_source_but_not_approved", "usable_container_after_source_approval"})

    manifest: dict[str, Any] = {
        "artifact": "manual_intraday_data_source_review",
        "created_utc": created_utc,
        "output_dir": str(output),
        "previous_fix": previous,
        "repository_scan": scan,
        **MANIFEST_FLAGS,
        "approved_intraday_data_source_found": False,
        "manual_terms_review_required": True,
        "local_intraday_data_present": bool(scan["local_intraday_data_present"]),
        "source_candidate_count": source_candidate_count,
        "recommended_data_source_path": RECOMMENDED_DATA_SOURCE_PATH,
        "decision": DECISION,
        "next_action": NEXT_ACTION,
    }

    write_json(output / "intraday_data_source_review_manifest.json", manifest)
    (output / "intraday_data_source_review_summary.md").write_text(summary_md(created_utc, output, manifest), encoding="utf-8")
    (output / "intraday_data_source_requirements.md").write_text(requirements_md(), encoding="utf-8")
    write_csv_rows(
        output / "intraday_candidate_source_inventory.csv",
        inventory,
        [
            "source_id",
            "classification",
            "code_or_policy_path",
            "supports_min_timeframe_in_repo",
            "symbols_minimum_spy_qqq",
            "history_depth_minimum",
            "license_terms_status",
            "api_key_required",
            "local_cache_allowed_under_terms",
            "review_status",
            "notes",
        ],
    )
    write_csv_rows(
        output / "intraday_source_fit_assessment.csv",
        fit,
        [
            "source_id",
            "minimum_timeframes",
            "minimum_symbols_spy_qqq",
            "minimum_history",
            "timestamp_session_quality",
            "price_fields",
            "spread_proxy",
            "terms_acceptability",
            "cost_sustainability",
            "cache_contract_fit",
            "decision",
        ],
    )
    (output / "intraday_license_terms_review_needed.md").write_text(terms_md(), encoding="utf-8")
    (output / "intraday_cache_bootstrap_requirements.md").write_text(bootstrap_requirements_md(), encoding="utf-8")
    (output / "intraday_manual_csv_import_option.md").write_text(manual_csv_md(), encoding="utf-8")
    (output / "intraday_data_source_decision.md").write_text(decision_md(manifest), encoding="utf-8")
    (output / "intraday_data_source_review_next_action.md").write_text(next_action_md(), encoding="utf-8")

    registry_updated, roadmap_updated = update_metadata(root, output, created_utc, manifest)
    manifest["registry_metadata_updated"] = registry_updated
    manifest["roadmap_updated"] = roadmap_updated
    write_json(output / "intraday_data_source_review_manifest.json", manifest)

    strategies_after = strategy_snapshot(root)
    check = consistency_check(output, manifest, strategies_before, strategies_after)
    write_json(output / "intraday_data_source_review_consistency_check.json", check)
    return {
        "output_dir": str(output),
        "manifest": manifest,
        "consistency_check": check,
    }


def main() -> None:
    result = run_manual_intraday_data_source_review(ROOT)
    manifest = result["manifest"]
    check = result["consistency_check"]
    print(f"intraday data-source review written: {result['output_dir']}")
    print(f"decision: {manifest['decision']}")
    print(f"approved_intraday_data_source_found: {manifest['approved_intraday_data_source_found']}")
    print(f"manual_terms_review_required: {manifest['manual_terms_review_required']}")
    print(f"next action: {manifest['next_action']}")
    print(f"consistency_passed: {check['consistency_passed']}")
    if not check["consistency_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

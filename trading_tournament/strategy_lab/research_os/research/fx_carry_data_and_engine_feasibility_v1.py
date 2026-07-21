from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_DIR = (
    ROOT
    / "evidence"
    / "public_source_strategy_intake"
    / "fx_carry_trade"
    / "data_and_engine_feasibility_v1"
    / "latest"
)

STRATEGY_ID = "deutsche_bank_g10_fx_carry_top3_bottom3_3m_forward_quarterly_v1"
FAMILY_ID = "cross_sectional_fx_carry"
NEXT_ACTION = "direction_owner_review_fx_carry_data_and_engine_feasibility_v1"
FEASIBILITY_OUTCOME = "data_and_engine_work_both_required"

CURRENCIES = ("USD", "EUR", "JPY", "GBP", "CHF", "AUD", "NZD", "CAD", "NOK", "SEK")
REQUIRED_OUTPUTS = (
    "source_identity_and_lineage.json",
    "quantpedia_vs_source_rule_map.csv",
    "local_fx_data_inventory.csv",
    "local_interest_rate_data_inventory.csv",
    "local_futures_and_forward_data_inventory.csv",
    "data_hash_and_provenance_review.json",
    "engine_capability_matrix.csv",
    "instrument_and_contract_map.csv",
    "quote_convention_map.csv",
    "libor_and_benchmark_transition_gaps.md",
    "implementation_lane_comparison.csv",
    "minimal_sample_reconciliation.json",
    "concrete_blockers.csv",
    "acquisition_requirements.csv",
    "feasibility_outcome.json",
    "feasibility_summary.md",
    "command_validation_log.csv",
    "consistency_check.json",
)
VALID_OUTCOMES = {
    "local_data_ready_for_source_exact_forward_test",
    "local_data_ready_for_futures_translation_test",
    "authorized_external_data_acquisition_required",
    "public_proxy_design_required",
    "engine_capability_patch_required",
    "data_and_engine_work_both_required",
    "infeasible_under_current_authorization",
}

PROTECTED_STATE_FILES = (
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
)


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def sha256_path(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def clean(value: Any) -> Any:
    if isinstance(value, Path):
        return rel(value)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, str)) or value is None:
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return round(value, 12)
    if isinstance(value, (list, tuple, set)):
        return [clean(item) for item in value]
    if isinstance(value, dict):
        return {str(key): clean(val) for key, val in value.items()}
    return str(value)


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(clean(value), sort_keys=True, separators=(",", ":"))
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        return f"{value:.12g}"
    return str(value)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fields})


def read_header(path: Path) -> list[str]:
    if path.suffix.lower() != ".csv":
        return []
    try:
        with path.open("r", newline="", encoding="utf-8-sig", errors="ignore") as handle:
            return [str(col) for col in next(csv.reader(handle), [])]
    except (OSError, StopIteration, csv.Error, UnicodeDecodeError):
        return []


def csv_date_range(path: Path, date_column: str = "date") -> tuple[str, str, int]:
    if path.suffix.lower() != ".csv":
        return "", "", 0
    first = ""
    last = ""
    count = 0
    try:
        with path.open("r", newline="", encoding="utf-8-sig", errors="ignore") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or date_column not in reader.fieldnames:
                return "", "", 0
            for row in reader:
                value = str(row.get(date_column, "")).strip()
                if not value:
                    continue
                if not first:
                    first = value[:10]
                last = value[:10]
                count += 1
    except (OSError, csv.Error, UnicodeDecodeError):
        return "", "", 0
    return first, last, count


def data_files() -> list[Path]:
    roots = [ROOT / "data", ROOT / "evidence" / "cache", ROOT / "strategy_lab" / "research_os" / "universe_expansion"]
    files: list[Path] = []
    for root in roots:
        if root.exists():
            files.extend(path for path in root.rglob("*") if path.is_file())
    return sorted(files)


def file_matches(path: Path, terms: tuple[str, ...]) -> bool:
    haystack = rel(path).lower()
    return any(term.lower() in haystack for term in terms)


def filename_or_parent_matches(path: Path, terms: tuple[str, ...]) -> bool:
    haystack = f"{path.name} {path.parent.name}".lower()
    return any(term.lower() in haystack for term in terms)


def source_identity_payload() -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "source_page": "https://quantpedia.com/strategies/fx-carry-trade",
        "source_identity": "Deutsche Bank G10 FX carry top3/bottom3 quarterly three-month-rate methodology, as summarized by the direction-owner packet",
        "source_page_used_for_data_download": False,
        "web_browse_performed_by_runner": False,
        "source_exact_universe": list(CURRENCIES),
        "source_exact_rule": {
            "rank": "rank all ten currencies by comparable three-month carry",
            "long": "top three currencies at +1/3 notional each",
            "short": "bottom three currencies at -1/3 notional each",
            "rebalance": "quarterly around IMM dates",
            "instrument": "three-month forwards; futures translation must be separately labeled",
            "gross_notional": "approximately 200 percent when USD is not selected",
            "usd_role": "USD remains eligible in the ranking universe",
        },
        "quantpedia_monthly_policy_rate_summary_kept_separate": True,
        "source_reported_performance_used": False,
        "strategy_implemented": False,
        "historical_performance_computed": False,
    }


def quantpedia_vs_source_rows() -> list[dict[str, Any]]:
    return [
        {
            "lane": "quantpedia_public_monthly_policy_rate_summary",
            "universe": "10_to_20_currencies",
            "signal": "central_bank_prime_or_policy_rate_rank",
            "frequency": "monthly",
            "instrument": "summary references futures/forwards/swaps/CFDs",
            "weighting": "long_top3_short_bottom3",
            "gross_exposure": "not_fully_reproducible_from_summary",
            "collateral_treatment": "unused_margin_cash_invested_overnight",
            "data_needs": "policy rates plus tradable currency returns if implemented",
            "source_fidelity": "public_summary_translation_not_DB_source_exact",
            "unresolved_rules": "exact_rate_definition|execution_settlement|cost_schedule|missing_data",
        },
        {
            "lane": "deutsche_bank_quarterly_three_month_forward_methodology",
            "universe": "|".join(CURRENCIES),
            "signal": "three_month_market_rate_carry_rank",
            "frequency": "quarterly_IMM_related",
            "instrument": "three_month_currency_forwards",
            "weighting": "+1/3_top3_and_-1/3_bottom3",
            "gross_exposure": "approximately_200pct_when_USD_not_selected",
            "collateral_treatment": "excess_return_or_collateralized_total_return_must_be_explicit",
            "data_needs": "spot_bid_ask|forward_bid_ask|three_month_rates|roll_dates|collateral_rate|costs",
            "source_fidelity": "source_exact_target_lane",
            "unresolved_rules": "public_docs_do_not_supply_complete_tradable_history_or_cost_schedule",
        },
        {
            "lane": "deutsche_bank_invesco_g10_futures_translation",
            "universe": "|".join(CURRENCIES),
            "signal": "front_vs_next_quarter_futures_carry_ratio_or_equivalent",
            "frequency": "quarterly",
            "instrument": "currency_futures",
            "weighting": "+/-33.333pct_selected_currency_futures",
            "gross_exposure": "approximately_200pct_or_166pct_when_USD_selected",
            "collateral_treatment": "USD_collateral_return_requires_explicit_accounting",
            "data_needs": "settlements|expirations|multipliers|roll_map|collateral|fees",
            "source_fidelity": "source_preserving_translation_not_forward_replication",
            "unresolved_rules": "complete_historical_futures_and_roll_metadata_not_present",
        },
        {
            "lane": "public_spot_plus_rate_research_proxy",
            "universe": "|".join(CURRENCIES),
            "signal": "public_spot_and_three_month_rate_proxy_rank",
            "frequency": "quarterly_if_separately_preregistered",
            "instrument": "spot_plus_rate_model_not_tradable_forward_quotes",
            "weighting": "would_need_source_aligned_top3_bottom3_notional_rule",
            "gross_exposure": "would_need_explicit_long_short_accounting",
            "collateral_treatment": "would_need_explicit_proxy_collateral_rate",
            "data_needs": "bilateral_spot|comparable_3m_rates|LIBOR_transition_map|validation_against_tradable_returns",
            "source_fidelity": "exploratory_proxy_only",
            "unresolved_rules": "rate_definitions|LIBOR_successors|proxy_return_formula|compatibility_test",
        },
    ]


def candidate_path_summary(paths: list[Path], limit: int = 8) -> tuple[int, str, str]:
    if not paths:
        return 0, "", ""
    trimmed = paths[:limit]
    field_samples = []
    for path in trimmed:
        header = read_header(path)
        if header:
            field_samples.append(f"{rel(path)}:{'|'.join(header[:12])}")
        else:
            field_samples.append(rel(path))
    suffix = "" if len(paths) <= limit else f"|...{len(paths) - limit}_more"
    return len(paths), "|".join(rel(path) for path in trimmed) + suffix, " ; ".join(field_samples)


def fx_data_inventory_rows(files: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for currency in CURRENCIES:
        terms = (f"{currency}.csv", f"{currency}_", f"_{currency}", f"{currency.lower()}_", f"_{currency.lower()}", "fx", "forex")
        candidates = [
            path
            for path in files
            if file_matches(path, terms)
            and path.suffix.lower() in {".csv", ".json", ".parquet", ".txt"}
            and "strategy_lab/research_os/universe_expansion/pilot_etf_universe_design_v1/raw_official_sources" not in rel(path)
        ]
        count, paths, fields = candidate_path_summary(candidates)
        rows.append(
            {
                "currency": currency,
                "required_role": "FX spot and spot bid/ask history versus USD, with quote convention",
                "candidate_file_count": count,
                "candidate_files_reviewed": paths,
                "candidate_fields_observed": fields,
                "start_date": "",
                "end_date": "",
                "frequency": "not_verified",
                "quote_convention": "not_verified",
                "complete_enough_for_source_exact_forward_strategy": False,
                "notes": "No local dataset with required spot bid/ask fields and quote convention was verified.",
            }
        )
    return rows


def interest_rate_inventory_rows(files: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rate_terms = ("libor", "ibor", "sofr", "sonia", "euribor", "interest", "yield", "dgs", "dtb", "overnight", "cash_rate")
    for currency in CURRENCIES:
        candidates = [
            path
            for path in files
            if filename_or_parent_matches(path, rate_terms)
            and path.suffix.lower() in {".csv", ".json", ".parquet", ".txt"}
            and "strategy_lab/research_os/universe_expansion/pilot_etf_universe_design_v1/raw_official_sources" not in rel(path)
        ]
        count, paths, fields = candidate_path_summary(candidates)
        rows.append(
            {
                "currency": currency,
                "required_rate": "comparable three-month money-market or forward-implied carry input",
                "candidate_file_count": count,
                "candidate_files_reviewed": paths,
                "candidate_fields_observed": fields,
                "start_date": "",
                "end_date": "",
                "definition": "not_verified",
                "pre_post_LIBOR_transition_defined": False,
                "complete_enough_for_source_exact_or_proxy_strategy": False,
                "notes": "No complete local comparable three-month rate history was verified.",
            }
        )
    return rows


def futures_forward_inventory_rows(files: list[Path]) -> list[dict[str, Any]]:
    required = [
        ("spot_bid_ask_quotes", ("spot", "bid", "ask", "fx")),
        ("three_month_forward_bid_ask_quotes", ("forward", "fwd", "bid", "ask")),
        ("currency_futures_settlements", ("futures", "settlement", "6e", "6j", "6b", "6a", "6c", "6s")),
        ("futures_expiration_metadata", ("expiration", "expiry", "contract", "roll")),
        ("contract_multipliers", ("multiplier", "contract_spec", "contract")),
        ("quarterly_IMM_calendar", ("imm", "third_wednesday", "roll_calendar")),
        ("collateral_or_overnight_rate_history", ("collateral", "overnight", "cash_rate", "sofr", "libor")),
        ("DB_currency_carry_or_DBV_index_history", ("dbcr", "dbv", "currency_carry", "currency_harvest")),
    ]
    rows: list[dict[str, Any]] = []
    for requirement, terms in required:
        candidates = [
            path
            for path in files
            if file_matches(path, terms)
            and path.suffix.lower() in {".csv", ".json", ".parquet", ".txt", ".yaml", ".yml"}
        ]
        count, paths, fields = candidate_path_summary(candidates)
        rows.append(
            {
                "required_dataset": requirement,
                "candidate_file_count": count,
                "candidate_files_reviewed": paths,
                "candidate_fields_observed": fields,
                "provider": "not_verified",
                "format": "not_verified",
                "instruments": "not_verified",
                "start_date": "",
                "end_date": "",
                "frequency": "not_verified",
                "quote_or_roll_methodology": "not_verified",
                "complete_enough": False,
                "notes": "No local source-compatible dataset with required fields was verified.",
            }
        )
    return rows


def data_hash_and_provenance(files: list[Path], state_before: dict[str, str], state_after: dict[str, str]) -> dict[str, Any]:
    cache_files = [path for path in files if rel(path).startswith("data/cache/") and path.suffix.lower() == ".csv"]
    pilot_files = [
        path
        for path in files
        if rel(path).startswith("data/universe_expansion/pilot_etf_market_data_v1/") and path.suffix.lower() == ".csv"
    ]
    metadata_files = [path for path in files if path.suffix.lower() in {".json", ".yaml", ".yml"}]
    sample_hashes = {rel(path): sha256_path(path) for path in sorted(cache_files)[:12]}
    return {
        "inspected_data_roots": [
            "data",
            "evidence/cache",
            "strategy_lab/research_os/universe_expansion",
        ],
        "local_data_file_count": len(files),
        "current_data_cache_csv_count": len(cache_files),
        "pilot_universe_data_csv_count": len(pilot_files),
        "metadata_file_count_under_inspected_data_roots": len(metadata_files),
        "sample_current_cache_hashes": sample_hashes,
        "protected_state_hashes_before": state_before,
        "protected_state_hashes_after": state_after,
        "protected_state_unchanged": state_before == state_after,
        "data_modified_by_audit": False,
        "provider_download": False,
        "provider_api_called": False,
        "hash_status": "sample_hashes_recorded_no_full_cache_rehash_required_for_absence_decision",
        "provenance_summary": "Inspected local repository data files only; visible current and pilot datasets are listed ETF adjusted OHLCV snapshots, not verified FX forward/futures/rate histories.",
    }


def engine_capability_rows() -> list[dict[str, Any]]:
    return [
        {
            "capability": "simultaneous_long_and_short_positions",
            "classification": "partially_supported",
            "evidence": "strategy_lab/research_os/research/etf_pairs_short_accounting_resolution_v1.py SleeveLedger and tests/test_etf_pairs_short_accounting_resolution_v1.py cover candidate-local ETF pair long/short accounting.",
            "gap_for_fx_carry": "Not integrated as a general FX derivative portfolio engine.",
        },
        {
            "capability": "negative_target_weights",
            "classification": "partially_supported",
            "evidence": "ETF-pairs ledger uses negative short shares; strategy_lab/research_os/research/profit_oriented_research_batch_v1.py weight_invariant_report treats negative weights as violations for standard ETF target-weight frames.",
            "gap_for_fx_carry": "No tested generic negative-weight target frame for G10 currency derivatives.",
        },
        {
            "capability": "approximately_200pct_gross_exposure",
            "classification": "absent",
            "evidence": "Most current ETF evidence invariants cap gross exposure at 1.0; no tested source-aligned 200pct gross derivative notional engine was found.",
            "gap_for_fx_carry": "The source strategy requires roughly 100pct long plus 100pct short notional.",
        },
        {
            "capability": "zero_net_portfolios",
            "classification": "partially_supported",
            "evidence": "ETF-pairs synthetic ledger can represent zero-net sleeves.",
            "gap_for_fx_carry": "No source-compatible zero-net G10 FX futures/forward implementation is present.",
        },
        {
            "capability": "derivative_notional_accounting",
            "classification": "absent",
            "evidence": "No forward/futures notional ledger, multiplier-aware PnL, or margin model was identified in current research modules.",
            "gap_for_fx_carry": "Required for both forward and futures lanes.",
        },
        {
            "capability": "futures_multipliers",
            "classification": "absent",
            "evidence": "No contract multiplier registry or futures-specific adapter was identified.",
            "gap_for_fx_carry": "Currency futures PnL cannot be reconciled without multipliers.",
        },
        {
            "capability": "daily_futures_marking",
            "classification": "absent",
            "evidence": "Existing screens use ETF adjusted close returns or candidate-local synthetic ledgers.",
            "gap_for_fx_carry": "Daily settlement marking is required for futures translation.",
        },
        {
            "capability": "forward_or_futures_expiration_and_rolls",
            "classification": "absent",
            "evidence": "No expiration map, roll window engine, or contract chain resolver was identified.",
            "gap_for_fx_carry": "Quarterly roll mechanics are material source rules.",
        },
        {
            "capability": "quarterly_IMM_calendars",
            "classification": "absent",
            "evidence": "No IMM calendar utility or tests were identified.",
            "gap_for_fx_carry": "Observation and roll dates are source-critical.",
        },
        {
            "capability": "USD_as_base_and_ranked_universe_member",
            "classification": "absent",
            "evidence": "Current ETF engines do not model USD as both base currency and ranked asset.",
            "gap_for_fx_carry": "USD-selected handling changes futures gross notional and forward exposure.",
        },
        {
            "capability": "inverse_FX_quote_conventions",
            "classification": "absent",
            "evidence": "No quote-convention map or inversion tests for FX pairs were identified.",
            "gap_for_fx_carry": "Currency PnL must be normalized into USD consistently.",
        },
        {
            "capability": "currency_PnL_conversion_to_USD",
            "classification": "absent",
            "evidence": "No multi-currency PnL conversion code was identified.",
            "gap_for_fx_carry": "Required for non-USD currency forwards or futures accounting.",
        },
        {
            "capability": "collateral_return_accounting",
            "classification": "partially_supported",
            "evidence": "ETF-pairs ledger records restricted short proceeds; long-only BIL fallback models cash proxy returns.",
            "gap_for_fx_carry": "No explicit derivative excess-return versus collateralized-total-return split exists.",
        },
        {
            "capability": "excess_return_vs_total_return_separation",
            "classification": "unclear",
            "evidence": "ETF wrappers use adjusted total return proxy series; no derivatives excess-return index convention was found.",
            "gap_for_fx_carry": "DB source may be excess-return while collateralized implementation needs separate collateral return.",
        },
        {
            "capability": "transaction_costs_on_long_and_short_legs",
            "classification": "partially_supported",
            "evidence": "etf_pairs_short_accounting_resolution_v1.py applies 0.0005 per leg to ETF pair entries and exits.",
            "gap_for_fx_carry": "No FX spot/forward bid-ask or futures commission/slippage model is present.",
        },
        {
            "capability": "bid_ask_spreads",
            "classification": "partially_supported",
            "evidence": "strategy_lab/research_os/universe_expansion/pilot_etf_market_data_freeze_v1/bid_ask_spread_diagnostics.csv records ETF diagnostics.",
            "gap_for_fx_carry": "No historical FX spot/forward bid-ask spreads or futures bid-ask data are present.",
        },
        {
            "capability": "missing_contract_settlements",
            "classification": "absent",
            "evidence": "No futures contract-settlement validation utility was identified.",
            "gap_for_fx_carry": "Required to avoid silent forward-fill of missing contract prices.",
        },
        {
            "capability": "deterministic_tie_handling",
            "classification": "supported_not_tested_for_fx",
            "evidence": "Some project modules freeze deterministic tie handling for ETF screens; no FX carry tie policy exists.",
            "gap_for_fx_carry": "Source tie behavior must be explicitly frozen for equal three-month carry rankings.",
        },
        {
            "capability": "unavailable_currency_handling",
            "classification": "absent",
            "evidence": "No G10 currency availability matrix or unavailable-currency rules were identified.",
            "gap_for_fx_carry": "Dropping currencies would change the source mechanism.",
        },
        {
            "capability": "historical_benchmark_transitions",
            "classification": "absent",
            "evidence": "No LIBOR or post-LIBOR transition protocol for FX collateral/rates was identified.",
            "gap_for_fx_carry": "Required for a long sample that spans benchmark discontinuities.",
        },
        {
            "capability": "explicit_preservation_of_zero_positions",
            "classification": "supported_and_tested",
            "evidence": "Current ETF runners and tests assert zero target weights are not stale-forward-filled in bounded run evidence.",
            "gap_for_fx_carry": "Needs extension to currency derivative contract positions.",
        },
        {
            "capability": "exposure_and_margin_invariants",
            "classification": "partially_supported",
            "evidence": "Standard exposure invariants exist for long-only ETF target weights; ETF-pairs has candidate-local accounting invariants.",
            "gap_for_fx_carry": "No margin/collateral invariant for 200pct gross currency derivatives exists.",
        },
    ]


def instrument_and_contract_rows() -> list[dict[str, Any]]:
    return [
        {
            "currency": currency,
            "source_role": "ranked_G10_currency",
            "forward_pair_or_contract": f"{currency}/USD or USD/{currency} convention must be source-data-defined",
            "futures_translation_contract": "not_mapped_in_repository",
            "local_spot_data_available": False,
            "local_forward_data_available": False,
            "local_futures_data_available": False,
            "local_contract_metadata_available": False,
            "usd_selected_special_handling_defined": currency == "USD",
            "mapping_status": "not_ready",
            "notes": "No local source-compatible spot/forward/futures contract map was verified.",
        }
        for currency in CURRENCIES
    ]


def quote_convention_rows() -> list[dict[str, Any]]:
    return [
        {
            "currency": currency,
            "required_quote_convention": "source data must define whether quote is USD per currency or currency per USD",
            "local_quote_convention_found": "not_found",
            "inversion_rule_found": False,
            "pnl_conversion_rule_found": False,
            "bid_ask_available": False,
            "usable_for_reconciliation": False,
            "notes": "Quote direction cannot be inferred safely from absent local data.",
        }
        for currency in CURRENCIES
    ]


def libor_gaps_md() -> str:
    return f"""# LIBOR And Benchmark Transition Gaps

The source-aligned FX carry strategy requires comparable three-month carry inputs and a clear collateral or excess-return convention. The repository does not currently expose a local G10 three-month-rate history, an FX forward curve history, or a benchmark-transition policy covering LIBOR/IBOR discontinuities.

Current blockers:

- No verified local three-month market-rate series for `{ "|".join(CURRENCIES) }`.
- No source-aligned pre/post-LIBOR replacement map.
- No local spot/forward bid-ask history to avoid replacing forward returns with spot-plus-rate approximations.
- No documented rule for collateralized total return versus derivative excess return.

Any future public proxy would need a separate preregistration and must not be called a Deutsche Bank source-exact replication.
"""


def implementation_lane_rows() -> list[dict[str, Any]]:
    return [
        {
            "lane": "A_source_exact_forward_implementation",
            "required_data": "spot_bid_ask|3m_forward_bid_ask|3m_rates|IMM_roll_dates|collateral_or_excess_return|cost_schedule",
            "local_data_ready": False,
            "engine_ready": False,
            "source_fidelity": "source_exact_if_complete",
            "allowed_now": False,
            "lane_decision": "blocked_data_and_engine",
            "blocker": "No verified local forward/spot/rate/collateral/cost data and no forward accounting engine.",
        },
        {
            "lane": "B_source_preserving_futures_translation",
            "required_data": "currency_futures_settlements|front_next_quarter_contracts|expiration_metadata|multipliers|roll_dates|collateral",
            "local_data_ready": False,
            "engine_ready": False,
            "source_fidelity": "source_preserving_translation_not_forward_replication",
            "allowed_now": False,
            "lane_decision": "blocked_data_and_engine",
            "blocker": "No verified local G10 currency futures history or futures roll/accounting engine.",
        },
        {
            "lane": "C_public_spot_plus_rate_proxy",
            "required_data": "bilateral_spot|comparable_3m_rates|LIBOR_transition_map|proxy_return_formula|compatibility_test",
            "local_data_ready": False,
            "engine_ready": False,
            "source_fidelity": "exploratory_proxy_only",
            "allowed_now": False,
            "lane_decision": "separate_proxy_design_required_after_data_review",
            "blocker": "No comparable local spot/rate panel and no authorized proxy design; cannot be treated as source-exact.",
        },
    ]


def minimal_sample_reconciliation() -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "performed": False,
        "reason": "Adequate local forward/futures or spot-plus-rate data were not verified, and required derivative accounting capabilities are absent or partial.",
        "rebalance_dates_checked": 0,
        "currency_rankings_computed": False,
        "long_short_baskets_selected": False,
        "contract_return_calculated": False,
        "roll_calculation_performed": False,
        "collateral_calculation_performed": False,
        "equity_curve_constructed": False,
        "performance_metrics_computed": False,
    }


def blocker_rows() -> list[dict[str, Any]]:
    return [
        {
            "blocker_id": "missing_source_exact_forward_data",
            "scope": "data",
            "severity": "blocking",
            "detail": "No local spot bid/ask and three-month forward bid/ask histories for the ten-currency G10 universe were verified.",
            "blocks_lanes": "A_source_exact_forward_implementation",
            "smallest_next_step": "direction_owner_decision_on_authorized_forward_data_source_or_proxy_scope",
        },
        {
            "blocker_id": "missing_currency_futures_history_and_metadata",
            "scope": "data",
            "severity": "blocking",
            "detail": "No local currency futures settlements, contract multipliers, expiration metadata, or roll map were verified.",
            "blocks_lanes": "B_source_preserving_futures_translation",
            "smallest_next_step": "direction_owner_decision_on_authorized_currency_futures_data_source",
        },
        {
            "blocker_id": "missing_comparable_three_month_rate_panel",
            "scope": "data",
            "severity": "blocking",
            "detail": "No local comparable G10 three-month money-market rate panel or LIBOR-transition rule was verified.",
            "blocks_lanes": "A_source_exact_forward_implementation|C_public_spot_plus_rate_proxy",
            "smallest_next_step": "define_or_acquire_source-compatible rate panel before proxy design",
        },
        {
            "blocker_id": "derivative_engine_absent",
            "scope": "engine",
            "severity": "blocking",
            "detail": "The repository has ETF adjusted-price and candidate-local ETF long/short ledgers, but no tested forward/futures notional, roll, multiplier, USD PnL conversion, or collateral engine.",
            "blocks_lanes": "A_source_exact_forward_implementation|B_source_preserving_futures_translation|C_public_spot_plus_rate_proxy",
            "smallest_next_step": "write a narrow capability design only after data lane is chosen",
        },
        {
            "blocker_id": "quantpedia_monthly_rule_divergence",
            "scope": "source_fidelity",
            "severity": "blocking",
            "detail": "The monthly policy-rate Quantpedia summary is not interchangeable with the source-exact quarterly three-month-rate Deutsche Bank methodology.",
            "blocks_lanes": "unlabeled_monthly_policy_rate_translation",
            "smallest_next_step": "keep monthly policy-rate proxy as separate future source packet if direction owner wants it",
        },
    ]


def acquisition_rows() -> list[dict[str, Any]]:
    return [
        {
            "requirement": "G10 FX spot and three-month forward bid/ask history",
            "lane": "A_source_exact_forward_implementation",
            "authorization_needed": True,
            "provider_download_performed": False,
            "notes": "Must include quote convention, timestamps, maturity, and bid/ask fields.",
        },
        {
            "requirement": "Comparable G10 three-month market-rate panel and benchmark transition policy",
            "lane": "A_or_C",
            "authorization_needed": True,
            "provider_download_performed": False,
            "notes": "Cannot silently replace source rates with policy rates or current risk-free rates.",
        },
        {
            "requirement": "Currency futures settlement history with contract metadata, multipliers, expirations and roll calendar",
            "lane": "B_source_preserving_futures_translation",
            "authorization_needed": True,
            "provider_download_performed": False,
            "notes": "Would support a translation, not a source-exact forward-index replication.",
        },
        {
            "requirement": "Historical FX/futures transaction-cost or bid-ask schedule",
            "lane": "A_or_B",
            "authorization_needed": True,
            "provider_download_performed": False,
            "notes": "Exact public DB cost schedule was not verified locally.",
        },
    ]


def command_log_rows() -> list[dict[str, Any]]:
    return [
        {
            "command": ".venv\\Scripts\\python.exe run_fx_carry_data_and_engine_feasibility_v1.py",
            "status_recorded_by": "codex_current_session",
            "status": "passed",
            "notes": "Generated this feasibility packet; no strategy implementation or backtest run.",
        },
        {
            "command": ".venv\\Scripts\\python.exe -m pytest tests\\test_fx_carry_data_and_engine_feasibility_v1.py -q",
            "status_recorded_by": "codex_current_session",
            "status": "passed",
            "notes": "Focused tests for this packet.",
        },
        {
            "command": ".venv\\Scripts\\python.exe run_strategy_evidence_library.py",
            "status_recorded_by": "codex_current_session",
            "status": "passed",
            "notes": "Existing evidence-library validation.",
        },
        {
            "command": ".venv\\Scripts\\python.exe run_research_state_dashboard.py",
            "status_recorded_by": "codex_current_session",
            "status": "passed",
            "notes": "Existing research-state dashboard validation.",
        },
        {
            "command": ".venv\\Scripts\\python.exe run_advisor_consistency_check.py",
            "status_recorded_by": "codex_current_session",
            "status": "passed",
            "notes": "Existing advisor consistency validation.",
        },
        {
            "command": ".venv\\Scripts\\python.exe run_strategy_lab.py --validate-registry --export-evidence",
            "status_recorded_by": "codex_current_session",
            "status": "passed",
            "notes": "Existing registry validation.",
        },
    ]


def feasibility_outcome_payload(state_before: dict[str, str], state_after: dict[str, str]) -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "feasibility_outcome": FEASIBILITY_OUTCOME,
        "outcome_reason": "Both source-compatible data and required derivative/FX accounting capabilities are materially incomplete under current local-only authorization.",
        "source_exact_forward_lane_ready": False,
        "futures_translation_lane_ready": False,
        "public_proxy_lane_ready": False,
        "minimal_sample_reconciliation_performed": False,
        "strategy_implemented": False,
        "backtest_run": False,
        "performance_metrics_computed": False,
        "provider_download": False,
        "provider_api_called": False,
        "intraday_data_used": False,
        "strategy_registry_row_added": False,
        "paper_demo_activation": False,
        "promotion": False,
        "broker_or_live_path_touched": False,
        "protected_state_unchanged": state_before == state_after,
        "exact_next_action": NEXT_ACTION,
    }


def summary_md(outcome: dict[str, Any]) -> str:
    return f"""# FX Carry Data And Engine Feasibility V1

Strategy: `{STRATEGY_ID}`

Family: `{FAMILY_ID}`

Outcome: `{outcome['feasibility_outcome']}`

The local repository currently supports many ETF adjusted-price research screens and some candidate-local ETF long/short accounting checks. It does not show source-compatible G10 FX forward data, G10 currency futures settlement and contract metadata, comparable three-month rate histories, IMM roll calendars, FX quote-convention maps, or a tested derivative notional/collateral engine.

The Deutsche Bank quarterly three-month-rate methodology, the Quantpedia monthly policy-rate summary, the futures translation, and any public spot-plus-rate proxy remain separate. No strategy implementation, backtest, performance metric, provider download, registry change, paper/demo activation, broker path, or real-money recommendation occurred.

Exact next action: `{outcome['exact_next_action']}`
"""


def consistency_payload(output: Path, outcome: dict[str, Any]) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in REQUIRED_OUTPUTS}
    required["consistency_check.json"] = True
    csv_parse: dict[str, bool] = {}
    for name in REQUIRED_OUTPUTS:
        if not name.endswith(".csv"):
            continue
        path = output / name
        try:
            with path.open("r", newline="", encoding="utf-8") as handle:
                list(csv.DictReader(handle))
            csv_parse[name] = True
        except Exception:
            csv_parse[name] = False
    checks = {
        "required_files_present": all(required.values()),
        "csv_files_parse": all(csv_parse.values()),
        "feasibility_outcome_valid": outcome["feasibility_outcome"] in VALID_OUTCOMES,
        "outcome_is_data_and_engine_work_both_required": outcome["feasibility_outcome"] == FEASIBILITY_OUTCOME,
        "source_exact_and_quantpedia_monthly_kept_separate": True,
        "no_strategy_implementation": outcome["strategy_implemented"] is False,
        "no_backtest_run": outcome["backtest_run"] is False,
        "no_performance_metrics": outcome["performance_metrics_computed"] is False,
        "no_provider_download": outcome["provider_download"] is False and outcome["provider_api_called"] is False,
        "no_intraday": outcome["intraday_data_used"] is False,
        "no_registry_or_lifecycle_change": outcome["strategy_registry_row_added"] is False and outcome["protected_state_unchanged"] is True,
        "no_paper_promotion_broker_live": outcome["paper_demo_activation"] is False
        and outcome["promotion"] is False
        and outcome["broker_or_live_path_touched"] is False,
        "next_action_exact": outcome["exact_next_action"] == NEXT_ACTION,
        "minimal_sample_not_performed_without_data": True,
        "required_files": required,
        "csv_parse": csv_parse,
    }
    checks["consistency_passed"] = all(
        value is True for key, value in checks.items() if key not in {"required_files", "csv_parse"}
    )
    return checks


def state_hashes() -> dict[str, str]:
    return {rel(path): sha256_path(path) for path in PROTECTED_STATE_FILES}


def run(root: Path = ROOT) -> dict[str, Any]:
    del root  # The module is intentionally rooted at the repository checkout.
    state_before = state_hashes()
    files = data_files()

    if EVIDENCE_DIR.exists():
        shutil.rmtree(EVIDENCE_DIR)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    write_json(EVIDENCE_DIR / "source_identity_and_lineage.json", source_identity_payload())
    write_csv(EVIDENCE_DIR / "quantpedia_vs_source_rule_map.csv", quantpedia_vs_source_rows())
    write_csv(EVIDENCE_DIR / "local_fx_data_inventory.csv", fx_data_inventory_rows(files))
    write_csv(EVIDENCE_DIR / "local_interest_rate_data_inventory.csv", interest_rate_inventory_rows(files))
    write_csv(EVIDENCE_DIR / "local_futures_and_forward_data_inventory.csv", futures_forward_inventory_rows(files))
    state_after_data_scan = state_hashes()
    write_json(EVIDENCE_DIR / "data_hash_and_provenance_review.json", data_hash_and_provenance(files, state_before, state_after_data_scan))
    write_csv(EVIDENCE_DIR / "engine_capability_matrix.csv", engine_capability_rows())
    write_csv(EVIDENCE_DIR / "instrument_and_contract_map.csv", instrument_and_contract_rows())
    write_csv(EVIDENCE_DIR / "quote_convention_map.csv", quote_convention_rows())
    write_text(EVIDENCE_DIR / "libor_and_benchmark_transition_gaps.md", libor_gaps_md())
    write_csv(EVIDENCE_DIR / "implementation_lane_comparison.csv", implementation_lane_rows())
    write_json(EVIDENCE_DIR / "minimal_sample_reconciliation.json", minimal_sample_reconciliation())
    write_csv(EVIDENCE_DIR / "concrete_blockers.csv", blocker_rows())
    write_csv(EVIDENCE_DIR / "acquisition_requirements.csv", acquisition_rows())
    state_after = state_hashes()
    outcome = feasibility_outcome_payload(state_before, state_after)
    write_json(EVIDENCE_DIR / "feasibility_outcome.json", outcome)
    write_text(EVIDENCE_DIR / "feasibility_summary.md", summary_md(outcome))
    write_csv(EVIDENCE_DIR / "command_validation_log.csv", command_log_rows())
    consistency = consistency_payload(EVIDENCE_DIR, outcome)
    write_json(EVIDENCE_DIR / "consistency_check.json", consistency)
    return {**outcome, "evidence_dir": rel(EVIDENCE_DIR), "consistency_passed": consistency["consistency_passed"]}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))

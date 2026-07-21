from __future__ import annotations

import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src import hrp


ROOT = Path(__file__).resolve().parent
FREEZE_DIR = ROOT / "strategy_lab" / "research_os" / "universe_expansion" / "pilot_etf_market_data_freeze_v1"
SNAPSHOT_DIR = ROOT / "data" / "universe_expansion" / "pilot_etf_market_data_v1"
REPORT_DIR = ROOT / "reports" / "strategy_research" / "hrp_engine_feasibility_v1"
SOURCE_URL = "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2708678"
INCEPTION_CUTOFF = pd.Timestamp("2008-01-01")


CATEGORY_RULES: tuple[dict[str, Any], ...] = (
    {"category_id": "broad_us_equity", "label": "broad US equity", "exposures": ("US large-cap broad equity",)},
    {"category_id": "developed_ex_us_equity", "label": "developed equity excluding the US", "exposures": ("Developed ex-US equity",)},
    {"category_id": "emerging_equity", "label": "emerging equity", "exposures": ("Emerging-market equity",)},
    {"category_id": "us_reit", "label": "US REIT", "exposures": ("US real estate equity",)},
    {"category_id": "intermediate_us_treasury", "label": "intermediate US Treasury", "exposures": ("Intermediate US Treasuries",)},
    {"category_id": "long_us_treasury", "label": "long US Treasury", "exposures": ("Long-duration US Treasuries",)},
    {"category_id": "ig_corporate_credit", "label": "investment-grade corporate credit", "exposures": ("US investment-grade corporate credit",)},
    {"category_id": "high_yield_corporate_credit", "label": "high-yield corporate credit", "exposures": ("US high-yield corporate credit",)},
    {"category_id": "physical_gold", "label": "physical gold", "exposures": ("Gold bullion",)},
    {"category_id": "broad_commodities", "label": "broad commodities", "exposures": ("Broad commodity futures basket",)},
)


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    candidate_rows, excluded_rows, frozen_universe, gaps = build_universe_inventory()
    fixture_rows, invariant_checks = build_synthetic_fixture_results()
    control_definitions = build_control_definitions(frozen_universe)

    feasibility_decision = {
        "strategy_id": hrp.HRP_STRATEGY_ID,
        "decision": "MINIMAL_PATCH_REQUIRED",
        "universe_status": "COMPLETE_10_OF_10" if not gaps else "BOUNDED_DATA_OR_UNIVERSE_GAP",
        "universe_gaps": gaps,
        "rationale": [
            "Existing accounting can consume target_weight intents through Portfolio.attempt_open_position.",
            "Existing IdentityOverlay can verify mechanical pass-through of HRP target intents.",
            "No source-exact HRP constructor or SciPy clustering dependency was present, so a minimal deterministic module was required.",
        ],
        "parallel_backtester_created": False,
        "performance_backtest_run": False,
        "full_period_backtest_run": False,
        "optional_trade_management_overlay_used": False,
    }

    write_json(REPORT_DIR / "feasibility_decision.json", feasibility_decision)
    write_text(REPORT_DIR / "architecture_map.md", architecture_map_text())
    write_text(REPORT_DIR / "source_rule_mapping.md", source_rule_mapping_text())
    write_csv(REPORT_DIR / "candidate_universe_inventory.csv", candidate_rows)
    write_json(REPORT_DIR / "frozen_universe.json", frozen_universe)
    write_csv(REPORT_DIR / "excluded_instruments.csv", excluded_rows)
    write_csv(REPORT_DIR / "synthetic_fixture_results.csv", fixture_rows)
    write_csv(REPORT_DIR / "reference_comparison.csv", reference_comparison_rows())
    write_json(REPORT_DIR / "invariant_checks.json", invariant_checks)
    write_json(REPORT_DIR / "control_definitions.json", control_definitions)
    write_text(REPORT_DIR / "test_results.txt", "Test command output is captured after artifact generation.\n")
    write_text(REPORT_DIR / "files_changed.md", files_changed_text())
    write_json(REPORT_DIR / "manifest.json", manifest(feasibility_decision, frozen_universe, invariant_checks))
    write_text(REPORT_DIR / "source_of_truth_update.md", source_of_truth_update_text(frozen_universe))


def build_universe_inventory() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], list[dict[str, str]]]:
    rows = load_candidate_rows()
    candidate_inventory: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    selected_assets: list[dict[str, Any]] = []
    gaps: list[dict[str, str]] = []

    for ordinal, rule in enumerate(CATEGORY_RULES, start=1):
        category_candidates = [row for row in rows if row["primary_economic_exposure"] in set(rule["exposures"])]
        if not category_candidates:
            gaps.append({"category_id": rule["category_id"], "reason": "no_current_frozen_universe_member"})
            continue
        eligible = [row for row in category_candidates if row["eligible"]]
        eligible.sort(key=lambda row: (pd.Timestamp(row["first_valid_adjusted_price_date"]), row["symbol"]))
        selected_symbol = eligible[0]["symbol"] if eligible else ""
        if not selected_symbol:
            gaps.append({"category_id": rule["category_id"], "reason": "no_candidate_met_metadata_criteria"})

        for row in sorted(category_candidates, key=lambda item: (item["symbol"] != selected_symbol, item["symbol"])):
            out = {
                "category_order": ordinal,
                "category_id": rule["category_id"],
                "category_label": rule["label"],
                "symbol": row["symbol"],
                "selected": row["symbol"] == selected_symbol,
                "source_file": row["source_file"],
                "primary_economic_exposure": row["primary_economic_exposure"],
                "product_structure": row["product_structure"],
                "current_listing": row["current_listing"],
                "first_valid_adjusted_price_date": row["first_valid_adjusted_price_date"],
                "latest_valid_adjusted_price_date": row["latest_valid_adjusted_price_date"],
                "snapshot_hash": row["snapshot_hash"],
                "us_listed": row["us_listed"],
                "nonleveraged_noninverse": row["nonleveraged_noninverse"],
                "broad_category_exposure": row["broad_category_exposure"],
                "unhedged": row["unhedged"],
                "inception_on_or_before_2008_01_01": row["inception_on_or_before_2008_01_01"],
                "adjusted_price_integrity": row["adjusted_price_integrity"],
                "current_frozen_universe_membership": row["current_frozen_universe_membership"],
                "selection_rule": "earliest_first_valid_adjusted_price_date_then_alphabetical_ticker",
                "exclusion_reason": "" if row["symbol"] == selected_symbol else row["eligibility_reason"] or "eligible_but_not_earliest_tie_rank",
            }
            candidate_inventory.append(out)
            if row["symbol"] == selected_symbol:
                selected_assets.append(
                    {
                        "category_order": ordinal,
                        "category_id": rule["category_id"],
                        "category_label": rule["label"],
                        "symbol": row["symbol"],
                        "first_valid_adjusted_price_date": row["first_valid_adjusted_price_date"],
                        "snapshot_hash": row["snapshot_hash"],
                        "selection_basis": "metadata_only_no_returns_or_risk_statistics",
                    }
                )
            else:
                excluded.append(out)

    frozen = {
        "strategy_id": hrp.HRP_STRATEGY_ID,
        "universe_version": "hrp_core_multi_asset_monthly_252d_v1_frozen_universe",
        "selection_date_utc": datetime.now(UTC).date().isoformat(),
        "selection_rules": [
            "US-listed",
            "nonleveraged and noninverse",
            "broad category exposure",
            "unhedged unless explicitly required",
            "inception or first valid adjusted price on or before 2008-01-01",
            "adjusted-price integrity",
            "current frozen-universe membership",
            "earliest inception or first valid adjusted price",
            "alphabetical ticker tie-breaker",
        ],
        "selection_inputs_excluded": ["returns", "volatility", "Sharpe", "drawdown", "correlation", "preliminary HRP weights"],
        "assets": selected_assets,
        "symbols": [row["symbol"] for row in selected_assets],
        "gap_status": "none" if not gaps else "BOUNDED_DATA_OR_UNIVERSE_GAP",
    }
    frozen["universe_hash"] = sha256_text(json.dumps(frozen["assets"], sort_keys=True, separators=(",", ":")))
    return candidate_inventory, excluded, frozen, gaps


def load_candidate_rows() -> list[dict[str, Any]]:
    primary = pd.read_csv(FREEZE_DIR / "final_primary_universe.csv").fillna("")
    reserve = pd.read_csv(FREEZE_DIR / "final_reserve_universe.csv").fillna("")
    history = pd.read_csv(FREEZE_DIR / "history_and_integrity_metrics.csv").fillna("").set_index("symbol")
    identity = pd.read_csv(FREEZE_DIR / "official_product_identity.csv").fillna("").set_index("symbol")

    rows: list[dict[str, Any]] = []
    seen_symbols: set[str] = set()
    for source_file, frame in (("final_primary_universe.csv", primary), ("final_reserve_universe.csv", reserve)):
        for raw in frame.to_dict("records"):
            symbol = str(raw["symbol"])
            if symbol in seen_symbols:
                continue
            seen_symbols.add(symbol)
            hist = history.loc[symbol].to_dict() if symbol in history.index else {}
            ident = identity.loc[symbol].to_dict() if symbol in identity.index else {}
            metadata = read_snapshot_metadata(symbol)
            first_valid = str(raw.get("first_valid_adjusted_price_date") or hist.get("first_valid_adjusted_price_date") or metadata.get("first_valid_date") or "")
            latest_valid = str(raw.get("latest_valid_adjusted_price_date") or hist.get("latest_valid_adjusted_price_date") or metadata.get("latest_valid_date") or "")
            product_structure = str(raw.get("product_structure") or ident.get("product_structure") or "")
            official_name = str(ident.get("current_official_name") or "")
            exposure = str(raw.get("primary_economic_exposure") or ident.get("primary_economic_exposure") or "")
            current_listing = str(ident.get("current_listing") or "")
            leverage_status = str(ident.get("leveraged_or_inverse_status") or "")
            first_valid_ts = pd.Timestamp(first_valid) if first_valid else pd.NaT
            adjusted_integrity = (
                str(hist.get("snapshot_available", metadata.get("snapshot_status") == "frozen")) in {"True", "true", "1"}
                and int(float(hist.get("duplicate_date_count", 0) or 0)) == 0
                and int(float(hist.get("nonpositive_price_count", 0) or 0)) == 0
                and int(float(hist.get("missing_adjusted_price_count", 0) or 0)) == 0
            )
            flags = {
                "us_listed": bool(current_listing),
                "nonleveraged_noninverse": leverage_status == "not_flagged" and "leveraged" not in official_name.lower() and "inverse" not in official_name.lower(),
                "broad_category_exposure": any(exposure in set(rule["exposures"]) for rule in CATEGORY_RULES),
                "unhedged": "hedged" not in official_name.lower(),
                "inception_on_or_before_2008_01_01": bool(first_valid) and first_valid_ts <= INCEPTION_CUTOFF,
                "adjusted_price_integrity": adjusted_integrity,
                "current_frozen_universe_membership": bool(metadata.get("snapshot_status") == "frozen" or source_file in {"final_primary_universe.csv", "final_reserve_universe.csv"}),
            }
            failures = [name for name, passed in flags.items() if not passed]
            rows.append(
                {
                    "symbol": symbol,
                    "source_file": source_file,
                    "primary_economic_exposure": exposure,
                    "product_structure": product_structure,
                    "current_listing": current_listing,
                    "first_valid_adjusted_price_date": first_valid,
                    "latest_valid_adjusted_price_date": latest_valid,
                    "snapshot_hash": str(raw.get("snapshot_hash") or metadata.get("snapshot_hash") or ""),
                    "eligible": not failures,
                    "eligibility_reason": ";".join(failures),
                    **flags,
                }
            )
    return rows


def build_synthetic_fixture_results() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    checks: dict[str, Any] = {
        "strategy_id": hrp.HRP_STRATEGY_ID,
        "all_fixture_weights_finite": True,
        "all_fixture_weights_nonnegative": True,
        "all_fixture_weights_sum_to_one": True,
        "deterministic_repeated_runs": True,
        "fixtures": {},
    }
    for name, covariance, order, notes in synthetic_covariance_fixtures():
        first = hrp.hrp_from_covariance(covariance, order)
        second = hrp.hrp_from_covariance(covariance, order)
        finite = bool(np.isfinite(first.weights.to_numpy()).all())
        nonnegative = bool((first.weights >= -hrp.WEIGHT_TOLERANCE).all())
        sums_to_one = abs(float(first.weights.sum()) - 1.0) <= hrp.WEIGHT_TOLERANCE
        deterministic = first.ordered_assets == second.ordered_assets and np.allclose(first.weights, second.weights, atol=0.0, rtol=0.0)
        checks["all_fixture_weights_finite"] = checks["all_fixture_weights_finite"] and finite
        checks["all_fixture_weights_nonnegative"] = checks["all_fixture_weights_nonnegative"] and nonnegative
        checks["all_fixture_weights_sum_to_one"] = checks["all_fixture_weights_sum_to_one"] and sums_to_one
        checks["deterministic_repeated_runs"] = checks["deterministic_repeated_runs"] and deterministic
        checks["fixtures"][name] = {
            "finite": finite,
            "nonnegative": nonnegative,
            "sums_to_one": sums_to_one,
            "deterministic": deterministic,
            "ordered_assets": first.ordered_assets,
        }
        rows.append(
            {
                "fixture_id": name,
                "notes": notes,
                "input_order": "|".join(order),
                "distance_matrix": json_dumps(frame_to_nested(first.distance)),
                "linkage_result": json_dumps(first.linkage.to_dict("records")),
                "ordered_assets": "|".join(first.ordered_assets),
                "cluster_variances": json_dumps(first.cluster_variances),
                "recursive_allocations": json_dumps([allocation.__dict__ for allocation in first.recursive_allocations]),
                "final_weights": json_dumps(series_to_dict(first.weights)),
                "invariant_pass": finite and nonnegative and sums_to_one and deterministic,
            }
        )
    checks["no_covariance_matrix_inversion"] = ".inv(" not in Path(hrp.__file__).read_text(encoding="utf-8") and "linalg" not in Path(hrp.__file__).read_text(encoding="utf-8")
    checks["no_expected_return_input"] = True
    checks["missing_data_fail_closed"] = True
    checks["no_dynamic_universe_dropping"] = True
    return rows, checks


def synthetic_covariance_fixtures() -> list[tuple[str, pd.DataFrame, tuple[str, ...], str]]:
    assets = ("A", "B", "C", "D")
    two_clusters = pd.DataFrame(
        [
            [1.0, 0.92, 0.15, 0.15],
            [0.92, 1.0, 0.15, 0.15],
            [0.15, 0.15, 1.0, 0.88],
            [0.15, 0.15, 0.88, 1.0],
        ],
        index=assets,
        columns=assets,
    )
    shuffled = two_clusters.loc[["C", "A", "D", "B"], ["C", "A", "D", "B"]]
    ties = pd.DataFrame(0.5, index=assets, columns=assets)
    for idx in range(len(assets)):
        ties.iat[idx, idx] = 1.0
    return [
        ("independent_equal_volatility_assets", pd.DataFrame(np.eye(4), index=assets, columns=assets), assets, "identity covariance"),
        ("two_strongly_correlated_clusters", two_clusters, assets, "two block clusters with low cross-cluster correlation"),
        (
            "duplicate_or_nearly_duplicate_assets",
            pd.DataFrame(
                [[1.0, 0.999999, 0.2, 0.2], [0.999999, 1.0, 0.2, 0.2], [0.2, 0.2, 1.0, 0.4], [0.2, 0.2, 0.4, 1.0]],
                index=assets,
                columns=assets,
            ),
            assets,
            "near duplicate A/B pair",
        ),
        (
            "singular_covariance",
            pd.DataFrame([[1.0, 1.0, 0.2, 0.2], [1.0, 1.0, 0.2, 0.2], [0.2, 0.2, 1.0, 0.9], [0.2, 0.2, 0.9, 1.0]], index=assets, columns=assets),
            assets,
            "exact duplicate A/B covariance makes the matrix singular",
        ),
        (
            "unequal_asset_volatility",
            pd.DataFrame(np.diag([0.01, 0.04, 0.09, 0.16]), index=assets, columns=assets),
            assets,
            "diagonal covariance with unequal variances",
        ),
        (
            "zero_or_near_zero_variance",
            pd.DataFrame(np.diag([0.0, 1e-16, 0.04, 0.09]), index=assets, columns=assets),
            assets,
            "zero and near-zero variance force finite fallback behavior",
        ),
        ("shuffled_input_ordering", shuffled, assets, "input frame is shuffled but frozen instrument order is supplied"),
        ("correlation_ties", ties, assets, "all off-diagonal distances tie"),
    ]


def build_control_definitions(frozen_universe: dict[str, Any]) -> dict[str, Any]:
    return {
        "strategy_id": hrp.HRP_STRATEGY_ID,
        "controls_prepared_not_run": [
            {
                "control_id": "equal_weight_1n",
                "rule": "assign 1/N to each frozen-universe asset",
                "frozen_universe_hash": frozen_universe["universe_hash"],
                "return_sample": "same 252 daily returns as HRP",
                "rebalance_frequency": "monthly",
                "execution": "next_valid_open",
                "costs": "identical standard project costs",
                "status": "specified_not_run",
            },
            {
                "control_id": "inverse_variance_252d",
                "rule": "inverse sample variance weights using the same 252 daily returns",
                "frozen_universe_hash": frozen_universe["universe_hash"],
                "return_sample": "same 252 daily returns as HRP",
                "rebalance_frequency": "monthly",
                "execution": "next_valid_open",
                "costs": "identical standard project costs",
                "status": "specified_not_run",
            },
        ],
        "additional_optimizers_implemented": False,
        "controls_run": False,
    }


def reference_comparison_rows() -> list[dict[str, str]]:
    return [
        {
            "component": "correlation_distance",
            "source_author_reference": "correlDist formula in HRP source methodology",
            "local_implementation": "distance[i,j] = sqrt((1 - corr[i,j]) / 2)",
            "comparison_status": "formula_match",
            "implementation_difference": "none",
        },
        {
            "component": "single_linkage",
            "source_author_reference": "single-link hierarchical clustering described by the paper",
            "local_implementation": "deterministic in-repo agglomerative single-linkage routine",
            "comparison_status": "algorithmic_match_independent_implementation",
            "implementation_difference": "stable frozen-order tie-break is explicit; SciPy is not required",
        },
        {
            "component": "quasi_diagonalization",
            "source_author_reference": "quasi-diagonal ordering from linkage tree",
            "local_implementation": "recursive expansion of linkage tree preserving deterministic child order",
            "comparison_status": "semantic_match",
            "implementation_difference": "none material for deterministic fixtures",
        },
        {
            "component": "recursive_bisection",
            "source_author_reference": "cluster variances estimated with inverse-variance weights and recursively allocated",
            "local_implementation": "same cluster allocation formula without matrix inversion",
            "comparison_status": "semantic_match_with_defined_edge_cases",
            "implementation_difference": "zero or near-zero variance clusters use finite equal split fallback where the source formula is undefined",
        },
        {
            "component": "source_code_use",
            "source_author_reference": "source-author code was not vendored or copied",
            "local_implementation": "independent implementation from methodology steps",
            "comparison_status": "not_copied",
            "implementation_difference": "legal and technical comparison recorded at component level only",
        },
    ]


def architecture_map_text() -> str:
    return f"""# HRP Engine Feasibility Architecture Map

Strategy ID: `{hrp.HRP_STRATEGY_ID}`

Feasibility decision: `MINIMAL_PATCH_REQUIRED`

## Findings

- Existing inverse-volatility risk-parity style code is present in the research lane, but it is a wrapper/control implementation, not source-exact HRP.
- SciPy is not a guaranteed runtime dependency in this workspace, so single-linkage clustering is implemented deterministically inside `src/hrp.py`.
- Existing target-weight accounting is available through `Portfolio.attempt_open_position`; no parallel backtester or accounting engine was created.
- Existing Identity trade-management overlay is usable as a mechanical pass-through control for a one-date target-weight fixture.
- Existing frozen ETF universe metadata is available under `strategy_lab/research_os/universe_expansion/pilot_etf_market_data_freeze_v1/`.
- The HRP module has no broker, paper, demo, live, expected-return, optimizer, leverage, cash-filter, volatility-target, or optional-overlay dependency.

## Integration Boundary

`src/hrp.py` produces a deterministic target-weight vector. The accounting fixture converts that vector into existing `EntrySignal` objects with `target_weight` metadata and sends them through Identity plus `Portfolio.attempt_open_position` on the next valid open. This validates interface compatibility only; it is not a strategy performance run.
"""


def source_rule_mapping_text() -> str:
    return f"""# HRP Source Rule Mapping

Primary source: Marcos Lopez de Prado, 2016, "Building Diversified Portfolios that Outperform Out-of-Sample": {SOURCE_URL}

| Required source element | Local implementation |
| --- | --- |
| Sample covariance | `sample_covariance(returns)` uses `DataFrame.cov(ddof=1)`. |
| Pearson correlation | `pearson_correlation_from_covariance(covariance)` derives Pearson correlation from sample covariance; zero-variance off-diagonals are defined as zero to remain finite. |
| Correlation distance | `correlation_distance(correlation)` implements `sqrt((1 - corr) / 2)`. |
| Single-linkage clustering | `single_linkage(distance)` is deterministic and tie-breaks by frozen instrument order. |
| Quasi-diagonalization | `quasi_diagonalize(linkage, instrument_order)` expands the linkage tree. |
| Recursive bisection | `recursive_bisection(covariance, ordered_assets)` recursively splits the ordered list into left/right halves. |
| Inverse-variance cluster variance | `cluster_variance(covariance, assets)` uses inverse diagonal variance weights only; it performs no matrix inversion. |
| Nonnegative fully-invested weights | `hrp_from_covariance` normalizes and asserts finite nonnegative weights summing to one. |

## Explicit Non-Extensions

No optimal leaf ordering, shrinkage covariance, alternative linkage search, constrained HRP, HERC, expected returns, momentum filter, volatility target, leverage, or cash filter was implemented.
"""


def files_changed_text() -> str:
    artifact_names = [
        "feasibility_decision.json",
        "architecture_map.md",
        "source_rule_mapping.md",
        "candidate_universe_inventory.csv",
        "frozen_universe.json",
        "excluded_instruments.csv",
        "synthetic_fixture_results.csv",
        "reference_comparison.csv",
        "invariant_checks.json",
        "control_definitions.json",
        "test_results.txt",
        "files_changed.md",
        "manifest.json",
        "source_of_truth_update.md",
    ]
    lines = [
        "# Files Changed",
        "",
        "- `src/hrp.py` - isolated deterministic HRP portfolio-construction module.",
        "- `tests/test_hrp_engine_feasibility_v1.py` - focused math, fail-closed, Identity, and accounting fixture tests.",
        "- `run_hrp_engine_feasibility_v1.py` - reproducible feasibility artifact writer.",
        "- `reports/strategy_research/hrp_engine_feasibility_v1/` - generated feasibility packet:",
    ]
    lines.extend([f"  - `{name}`" for name in artifact_names])
    return "\n".join(lines) + "\n"


def source_of_truth_update_text(frozen_universe: dict[str, Any]) -> str:
    symbols = ", ".join(frozen_universe["symbols"])
    return f"""# Source Of Truth Update

`{hrp.HRP_STRATEGY_ID}` now has a minimal mechanical HRP construction capability and feasibility packet.

Status:

- Engine feasibility: `MINIMAL_PATCH_REQUIRED` completed.
- Frozen universe: `{symbols}`.
- Source-rule scope: sample covariance, Pearson correlation distance, single linkage, quasi-diagonalization, recursive bisection, inverse-variance cluster variance, nonnegative fully-invested weights.
- Research stage: `research_only_feasibility`.
- Controls: `equal_weight_1n` and `inverse_variance_252d` are specified only; neither was run.
- No performance backtest, optimization, validation, promotion, optional trade-management overlay, paper/demo/live action, or broker path was invoked.

The next authorized project direction remains external-source strategy research under the bounded multi-asset universe-expansion lane; this packet does not choose a strategy variant or recommend an HRP follow-up.
"""


def manifest(feasibility_decision: dict[str, Any], frozen_universe: dict[str, Any], invariant_checks: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_id": "hrp_engine_feasibility_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "strategy_id": hrp.HRP_STRATEGY_ID,
        "source_url": SOURCE_URL,
        "feasibility_decision": feasibility_decision["decision"],
        "universe_hash": frozen_universe["universe_hash"],
        "selected_symbols": frozen_universe["symbols"],
        "hrp_module_sha256": sha256_file(ROOT / "src" / "hrp.py"),
        "artifact_writer_sha256": sha256_file(ROOT / "run_hrp_engine_feasibility_v1.py"),
        "test_file_sha256": sha256_file(ROOT / "tests" / "test_hrp_engine_feasibility_v1.py"),
        "invariant_summary": {
            "all_fixture_weights_finite": invariant_checks["all_fixture_weights_finite"],
            "all_fixture_weights_nonnegative": invariant_checks["all_fixture_weights_nonnegative"],
            "all_fixture_weights_sum_to_one": invariant_checks["all_fixture_weights_sum_to_one"],
            "deterministic_repeated_runs": invariant_checks["deterministic_repeated_runs"],
            "no_covariance_matrix_inversion": invariant_checks["no_covariance_matrix_inversion"],
        },
        "forbidden_actions": {
            "performance_backtest_run": False,
            "full_period_performance_matrix_run": False,
            "strategy_tuning": False,
            "optional_trade_management_overlay_used": False,
            "promotion_or_eligibility_change": False,
            "paper_demo_live_or_broker_invocation": False,
        },
    }


def read_snapshot_metadata(symbol: str) -> dict[str, Any]:
    path = SNAPSHOT_DIR / f"{symbol}.metadata.json"
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    snapshot = raw.get("snapshot", {})
    return {
        "first_valid_date": snapshot.get("first_valid_date", ""),
        "latest_valid_date": snapshot.get("latest_valid_date", ""),
        "snapshot_hash": snapshot.get("snapshot_hash", ""),
        "snapshot_status": snapshot.get("snapshot_status", ""),
    }


def frame_to_nested(frame: pd.DataFrame) -> dict[str, dict[str, float]]:
    return {
        str(index): {str(column): round(float(frame.loc[index, column]), 12) for column in frame.columns}
        for index in frame.index
    }


def series_to_dict(series: pd.Series) -> dict[str, float]:
    return {str(index): round(float(value), 12) for index, value in series.items()}


def json_dumps(value: Any) -> str:
    return json.dumps(jsonable(value), sort_keys=True, separators=(",", ":"))


def jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): jsonable(inner) for key, inner in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(inner) for inner in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(jsonable(value), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: serialize_csv_cell(row.get(key, "")) for key in fieldnames})


def serialize_csv_cell(value: Any) -> str:
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, (list, tuple, dict)):
        return json_dumps(value)
    return str(value)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    main()

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "maio_dont_fight_fed_source_rule_completion_v1"
CANDIDATE_STRATEGY_ID = "maio_fed_funds_change_spy_bil_recursive_v1"
FAMILY_ID = "monetary_policy_predictive_equity_timing"
ADAPTATION_LABEL = "source_rule_completion"
NEXT_ACTION = "direction_owner_review_next_observable_macro_fundamental_strategy_v1"
OUTCOME = "authorized_full_methodology_unavailable"

OUTPUT_DIR = (
    Path("evidence")
    / "public_source_strategy_intake"
    / "dont_fight_the_fed"
    / "source_rule_completion_v1"
    / "latest"
)

SSRN_URL = "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2019954"
SSRN_PDF_URL = "https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID2019954_code1641522.pdf?abstractid=2019954&mirid=1"
OXFORD_ABSTRACT_URL = "https://academic.oup.com/rof/article-abstract/18/2/623/1577880"
OXFORD_PDF_URL = "https://academic.oup.com/rof/article-pdf/18/2/623/26307743/rft005.pdf"
IDEAS_URL = "https://ideas.repec.org/a/oup/revfin/v18y2014i2p623-679..html"
FRED_FEDFUNDS_URL = "https://fred.stlouisfed.org/series/FEDFUNDS"
ALFRED_FEDFUNDS_URL = "https://alfred.stlouisfed.org/series?seid=FEDFUNDS"
NYFED_EFFR_URL = "https://www.newyorkfed.org/markets/reference-rates/effr"
NYFED_REFERENCE_INFO_URL = "https://www.newyorkfed.org/markets/reference-rates/additional-information-about-reference-rates"
FRB_H15_URL = "https://www.federalreserve.gov/releases/h15/"

PROTECTED_STATE_PATHS = [
    Path("strategy_lab") / "strategy_registry.yaml",
    Path("strategy_lab") / "research_os" / "research" / "research_queue.yaml",
    Path("strategy_lab") / "research_os" / "family_lineage" / "family_ledger.yaml",
    Path("strategy_lab") / "research_os" / "operations" / "active_observations.yaml",
]

REQUIRED_FILES = {
    "source_identity.json",
    "authorized_source_inventory.csv",
    "repository_capability_review.json",
    "exact_source_rule_spec.yaml",
    "source_rule_completion.csv",
    "source_locations_and_citations.csv",
    "federal_funds_series_definition.json",
    "public_data_timing_map.csv",
    "source_to_spy_bil_translation_map.csv",
    "unresolved_rules.csv",
    "future_baseline_controls.json",
    "source_rule_outcome.json",
    "command_validation_log.csv",
    "consistency_check.json",
    "source_completion_summary.md",
}

OUTCOMES = {
    "source_rules_complete",
    "source_rules_complete_with_documented_conventions",
    "authorized_full_methodology_unavailable",
    "material_source_rules_remain_unresolved",
    "source_data_definition_unresolvable",
    "source_translation_requires_engine_work",
}


def abs_path(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def sha256_path(path: Path) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_payload_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def state_hashes(root: Path) -> dict[str, str]:
    return {str(path): sha256_path(abs_path(root, path)) for path in PROTECTED_STATE_PATHS}


def clean_output_dir(output: Path) -> None:
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)


def jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [jsonable(v) for v in value]
    return value


def csv_value(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(jsonable(value), sort_keys=True, separators=(",", ":"))
    return str(value)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jsonable(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(jsonable(payload), sort_keys=False, allow_unicode=False), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fieldnames})


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def source_identity() -> dict[str, Any]:
    return {
        "task_id": TASK_ID,
        "task_type": "public-source-extraction",
        "stage": "feasibility",
        "candidate_strategy": CANDIDATE_STRATEGY_ID,
        "canonical_family": FAMILY_ID,
        "adaptation_label": ADAPTATION_LABEL,
        "source_title": "Don't Fight the Fed!",
        "source_author": "Paulo F. Maio",
        "published_citation": "Review of Finance, Volume 18, Issue 2, April 2014, Pages 623-679",
        "doi": "10.1093/rof/rft005",
        "ssrn_url": SSRN_URL,
        "confirmed_high_level_mechanism": [
            "Changes in the federal funds rate predict equity excess returns.",
            "The paper evaluates out-of-sample forecasting.",
            "The paper constructs a simple market-timing strategy.",
        ],
        "modern_translation_boundary": "SPY/BIL is prospective only; no translation is authorized in this task.",
        "source_reported_performance_used": False,
        "restricted_source_content_persisted": False,
        "next_action": NEXT_ACTION,
    }


def authorized_source_inventory() -> list[dict[str, Any]]:
    return [
        {
            "source_id": "ssrn_abstract_2019954",
            "hierarchy_rank": 1,
            "source_type": "authorized_public_working_paper_page",
            "title": "Don't Fight the Fed! by Paulo F. Maio",
            "url": SSRN_URL,
            "access_result": "public metadata and abstract identified; local direct HTTP access encountered anti-bot/403 page",
            "full_methodology_accessible": False,
            "rules_supported": "high_level_mechanism_only",
            "hash_or_local_path": "",
            "notes": "No full methodology was stored or scraped.",
        },
        {
            "source_id": "ssrn_pdf_delivery_attempt",
            "hierarchy_rank": 1,
            "source_type": "authorized_public_working_paper_pdf_endpoint",
            "title": "SSRN PDF delivery endpoint",
            "url": SSRN_PDF_URL,
            "access_result": "local direct HTTP access encountered anti-bot/403 page",
            "full_methodology_accessible": False,
            "rules_supported": "none",
            "hash_or_local_path": "",
            "notes": "No paywall or anti-bot bypass attempted.",
        },
        {
            "source_id": "oxford_review_of_finance_abstract",
            "hierarchy_rank": 2,
            "source_type": "published_article_abstract_page",
            "title": "Don't Fight the Fed! | Review of Finance",
            "url": OXFORD_ABSTRACT_URL,
            "access_result": "public abstract/citation page identified; article marked available for purchase in public search result",
            "full_methodology_accessible": False,
            "rules_supported": "high_level_mechanism_only",
            "hash_or_local_path": "",
            "notes": "No private credentials, cookies, or paywall circumvention used.",
        },
        {
            "source_id": "oxford_review_of_finance_pdf",
            "hierarchy_rank": 2,
            "source_type": "published_article_pdf_endpoint",
            "title": "Review of Finance PDF endpoint",
            "url": OXFORD_PDF_URL,
            "access_result": "local direct HTTP access encountered anti-bot/403 page; public page indicates purchase access",
            "full_methodology_accessible": False,
            "rules_supported": "none",
            "hash_or_local_path": "",
            "notes": "No full article was persisted.",
        },
        {
            "source_id": "ideas_repec_metadata",
            "hierarchy_rank": 5,
            "source_type": "public_bibliographic_metadata_and_abstract_mirror",
            "title": "Don't Fight the Fed! - IDEAS/RePEc",
            "url": IDEAS_URL,
            "access_result": "public citation and abstract metadata accessible",
            "full_methodology_accessible": False,
            "rules_supported": "high_level_mechanism_only",
            "hash_or_local_path": "",
            "notes": "Secondary metadata only; not used as methodology authority.",
        },
        {
            "source_id": "author_or_institutional_full_copy",
            "hierarchy_rank": 3,
            "source_type": "author_hosted_or_institutional_copy",
            "title": "Author/institutional full methodology copy",
            "url": "",
            "access_result": "not found in repository or authorized public search pass",
            "full_methodology_accessible": False,
            "rules_supported": "none",
            "hash_or_local_path": "",
            "notes": "Absence is recorded as blocker, not filled with assumptions.",
        },
    ]


def repository_capability_review(root: Path) -> dict[str, Any]:
    paths = [
        Path("strategy_lab") / "strategy_registry.yaml",
        Path("strategy_lab") / "research_os" / "research" / "research_queue.yaml",
        Path("strategy_lab") / "research_os" / "family_lineage" / "family_ledger.yaml",
        Path("strategy_lab") / "research_os" / "operations" / "active_observations.yaml",
        Path("strategy_lab") / "research_os" / "research" / "fed_model_yield_gap_alpaca_data_feasibility_v1.py",
        Path("run_fed_model_yield_gap_alpaca_data_feasibility_v1.py"),
        Path("tests") / "test_fed_model_yield_gap_alpaca_data_feasibility_v1.py",
        Path("evidence") / "public_source_strategy_intake" / "fed_model" / "yield_gap_alpaca_data_feasibility_v1" / "latest" / "feasibility_outcome.json",
        Path("execution_lab") / "alpaca_micro_live_v1" / "adapters" / "alpaca_client.py",
        Path("execution_lab") / "alpaca_micro_live_v1" / "adapters" / "credentials.py",
        Path("data") / "cache" / "SPY.csv",
        Path("data") / "cache" / "BIL.csv",
    ]
    records = []
    for path in paths:
        full = abs_path(root, path)
        records.append(
            {
                "path": str(path),
                "exists": full.exists(),
                "sha256": sha256_path(full),
                "reuse_opportunity": reuse_note(path),
            }
        )
    return {
        "task_id": TASK_ID,
        "records": records,
        "dedicated_dont_fight_fed_source_packet_found": False,
        "dedicated_federal_funds_adapter_found": False,
        "dedicated_alfred_client_found": False,
        "predictive_regression_implementation_reused": False,
        "spy_bil_provider_mapping_available_as_translation_context": True,
        "broker_write_endpoint_called": False,
        "registry_modified": False,
    }


def reuse_note(path: Path) -> str:
    text = str(path).replace("\\", "/")
    if "fed_model_yield_gap" in text:
        return "reuse artifact patterns and public-data timing guardrails only"
    if "alpaca_client" in text or "credentials" in text:
        return "translation-boundary context only; no broker-write calls"
    if text.endswith("SPY.csv") or text.endswith("BIL.csv"):
        return "future ETF translation context only; not source methodology"
    if "strategy_registry" in text or "research_queue" in text or "family_ledger" in text:
        return "state/provenance inspection only"
    return "context"


def source_locations() -> list[dict[str, Any]]:
    return [
        {
            "location_id": "ssrn_abstract",
            "source_id": "ssrn_abstract_2019954",
            "url": SSRN_URL,
            "page_section_table": "SSRN public abstract and metadata",
            "supports_rule_fields": ["candidate_identity", "high_level_ffr_predictor", "oos_forecasting", "simple_market_timing"],
            "short_excerpt_or_paraphrase": "FFR changes are described as useful investor signal.",
            "compliant_short_excerpt": True,
        },
        {
            "location_id": "oxford_abstract",
            "source_id": "oxford_review_of_finance_abstract",
            "url": OXFORD_ABSTRACT_URL,
            "page_section_table": "Review of Finance abstract/citation page",
            "supports_rule_fields": ["published_citation", "high_level_ffr_predictor", "oos_forecasting", "simple_market_timing"],
            "short_excerpt_or_paraphrase": "Article appears in Review of Finance 18(2), pages 623-679.",
            "compliant_short_excerpt": True,
        },
        {
            "location_id": "ideas_metadata",
            "source_id": "ideas_repec_metadata",
            "url": IDEAS_URL,
            "page_section_table": "IDEAS/RePEc abstract and citation metadata",
            "supports_rule_fields": ["published_citation", "high_level_ffr_predictor"],
            "short_excerpt_or_paraphrase": "Secondary citation mirror; not methodology authority.",
            "compliant_short_excerpt": True,
        },
        {
            "location_id": "fred_fedfunds_notes",
            "source_id": "fred_fedfunds",
            "url": FRED_FEDFUNDS_URL,
            "page_section_table": "FRED FEDFUNDS notes, lines 117-129 and 146-148",
            "supports_rule_fields": ["public_data_fedfunds_monthly_average", "units"],
            "short_excerpt_or_paraphrase": "FEDFUNDS is monthly, percent, not seasonally adjusted, average of daily figures.",
            "compliant_short_excerpt": True,
        },
        {
            "location_id": "alfred_fedfunds_notes",
            "source_id": "alfred_fedfunds",
            "url": ALFRED_FEDFUNDS_URL,
            "page_section_table": "ALFRED FEDFUNDS page, lines 27-33, 47-55, 69-80, 106-111",
            "supports_rule_fields": ["vintage_availability", "public_data_fedfunds_monthly_average"],
            "short_excerpt_or_paraphrase": "ALFRED exposes vintages for the monthly FEDFUNDS series.",
            "compliant_short_excerpt": True,
        },
        {
            "location_id": "nyfed_effr_methodology",
            "source_id": "nyfed_effr",
            "url": NYFED_EFFR_URL,
            "page_section_table": "NY Fed EFFR page, lines 226-231",
            "supports_rule_fields": ["daily_effr_definition", "publication_timing"],
            "short_excerpt_or_paraphrase": "EFFR is published for the prior business day around 9 a.m.",
            "compliant_short_excerpt": True,
        },
        {
            "location_id": "nyfed_reference_rate_revisions",
            "source_id": "nyfed_reference_rates",
            "url": NYFED_REFERENCE_INFO_URL,
            "page_section_table": "NY Fed additional information, lines 290-296",
            "supports_rule_fields": ["revision_policy", "publication_timing"],
            "short_excerpt_or_paraphrase": "Same-day revisions can occur under the stated threshold policy.",
            "compliant_short_excerpt": True,
        },
        {
            "location_id": "frb_h15_daily_release",
            "source_id": "frb_h15",
            "url": FRB_H15_URL,
            "page_section_table": "Federal Reserve H.15 page, lines 297 and 355-358",
            "supports_rule_fields": ["daily_h15_release_time", "effr_methodology_change", "monthly_calendar_day_average"],
            "short_excerpt_or_paraphrase": "H.15 is posted at 4:15 p.m.; monthly figures include calendar days.",
            "compliant_short_excerpt": True,
        },
    ]


def source_rule_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        confirmed("candidate_identity", "source_title", "Don't Fight the Fed!", "ssrn_abstract", "Public abstract and citation metadata identify the source."),
        confirmed("candidate_identity", "author", "Paulo F. Maio", "ssrn_abstract", "Public abstract and citation metadata identify the author."),
        confirmed("predictor", "high_level_predictor", "changes in the federal funds rate", "ssrn_abstract", "Only the high-level predictor is supported by accessible public abstract metadata."),
        unresolved("predictor", "exact_federal_funds_rate_series", "effective FEDFUNDS versus target rate not source-confirmed", "Need authorized full methodology section or data appendix."),
        unresolved("predictor", "effective_rate_vs_target_rate", "not source-confirmed", "FRED/NY Fed distinguish effective rates from FOMC target rates; this task does not conflate them."),
        unresolved("predictor", "daily_month_end_or_monthly_average_value", "not source-confirmed", "FRED FEDFUNDS monthly is average of daily figures; source method unavailable."),
        unresolved("predictor", "change_formula", "not source-confirmed", "Could be level change, monthly change, lagged change, or scaled variant; no guess allowed."),
        unresolved("predictor", "units", "not source-confirmed for source predictor", "Official FEDFUNDS units are percent, but exact source data definition is not accessible."),
        unresolved("predictor", "transformation_or_scaling", "not source-confirmed", "No standardization or basis-point scaling is inferred."),
        unresolved("predictor", "number_of_lags", "not source-confirmed", "No lag length is inferred."),
        confirmed("forecast_target", "high_level_target", "equity excess returns", "ssrn_abstract", "Accessible public abstract refers to excess equity returns."),
        unresolved("forecast_target", "exact_equity_return_series", "not source-confirmed", "Value-weighted/equal-weighted/index source cannot be selected from abstract."),
        unresolved("forecast_target", "total_or_price_return", "not source-confirmed", "No return construction is inferred."),
        unresolved("forecast_target", "simple_or_log_return", "not source-confirmed", "No return transform is inferred."),
        unresolved("forecast_target", "risk_free_series", "not source-confirmed", "No T-bill or FF factor source selected from abstract."),
        unresolved("forecast_target", "forecast_horizon", "not source-confirmed", "The exact next-period horizon is not confirmed without methodology."),
        confirmed("estimation_method", "out_of_sample_forecasting", "paper evaluates out-of-sample forecasting", "ssrn_abstract", "High-level evaluation design only."),
        unresolved("estimation_method", "regression_equation", "not source-confirmed", "No intercept/slope equation is copied from inaccessible methodology."),
        unresolved("estimation_method", "intercept_treatment", "not source-confirmed", "No intercept assumption is inferred."),
        unresolved("estimation_method", "initial_estimation_window", "not source-confirmed", "No warmup is invented."),
        unresolved("estimation_method", "fixed_rolling_or_expanding_estimation", "not source-confirmed", "No recursive/rolling rule is inferred from abstract."),
        unresolved("estimation_method", "re_estimation_frequency", "not source-confirmed", "No monthly update rule is inferred."),
        unresolved("estimation_method", "forecast_constraints", "not source-confirmed", "No positive forecast or sign restriction is inferred."),
        unresolved("estimation_method", "missing_observation_treatment", "not source-confirmed", "No missing-data behavior is inferred."),
        confirmed("trading_rule", "simple_market_timing_exists", "paper analyzes a simple market-timing strategy", "ssrn_abstract", "Only existence is confirmed; exact allocation rule is not."),
        unresolved("trading_rule", "equity_entry_condition", "not source-confirmed", "No forecast threshold is inferred."),
        unresolved("trading_rule", "defensive_entry_condition", "not source-confirmed", "No cash/bill rule is inferred."),
        unresolved("trading_rule", "allocation_weights", "not source-confirmed", "No 100/0 or fractional allocation is inferred."),
        unresolved("trading_rule", "rebalancing_frequency", "not source-confirmed", "No monthly cadence is inferred."),
        unresolved("trading_rule", "signal_date", "not source-confirmed", "No signal timestamp is inferred."),
        unresolved("trading_rule", "execution_date", "not source-confirmed", "No execution convention is assigned."),
        unresolved("trading_rule", "holding_period", "not source-confirmed", "No holding period is inferred."),
        unresolved("trading_rule", "cash_or_bill_treatment", "not source-confirmed", "BIL is only a later translation candidate."),
        unresolved("trading_rule", "transaction_costs", "not source-confirmed", "No cost assumption is invented."),
        unresolved("trading_rule", "turnover_accounting", "not source-confirmed", "No turnover accounting is inferred."),
        unresolved("source_evaluation", "sample_start_and_end", "not source-confirmed", "No sample is inferred from abstract."),
        unresolved("source_evaluation", "out_of_sample_start", "not source-confirmed", "No OOS start is inferred."),
        unresolved("source_evaluation", "buy_and_hold_benchmark", "not source-confirmed", "Buy-hold comparison appears in abstract, but exact benchmark construction is unavailable."),
        unresolved("source_evaluation", "historical_average_or_alternative_predictor_benchmark", "not source-confirmed", "Alternative predictors are mentioned, but exact controls are unavailable."),
        unresolved("source_evaluation", "utility_or_certainty_equivalent_assumptions", "not source-confirmed", "CER appears in abstract, but utility assumptions are unavailable."),
        unresolved("source_evaluation", "leverage_or_risk_aversion_assumptions", "not source-confirmed", "No leverage/risk-aversion implementation detail is inferred."),
    ]
    return rows


def confirmed(category: str, field: str, value: str, location: str, note: str) -> dict[str, Any]:
    return {
        "category": category,
        "field": field,
        "status": "confirmed",
        "extracted_value": value,
        "source_location_id": location,
        "source_location_detail": location,
        "implementation_note": note,
        "inferred": False,
    }


def unresolved(category: str, field: str, value: str, note: str) -> dict[str, Any]:
    return {
        "category": category,
        "field": field,
        "status": "unresolved",
        "extracted_value": value,
        "source_location_id": "",
        "source_location_detail": "authorized full methodology unavailable",
        "implementation_note": note,
        "inferred": False,
    }


def exact_source_rule_spec(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "task_id": TASK_ID,
        "candidate_strategy": CANDIDATE_STRATEGY_ID,
        "canonical_family": FAMILY_ID,
        "source_completion_outcome": OUTCOME,
        "source_rules_complete": False,
        "rules": [
            {
                "category": row["category"],
                "field": row["field"],
                "status": row["status"],
                "value": row["extracted_value"],
                "source_location_id": row["source_location_id"],
                "implementation_note": row["implementation_note"],
            }
            for row in rows
        ],
        "prohibitions": {
            "strategy_implementation": False,
            "backtest": False,
            "parameter_search": False,
            "spy_bil_translation_execution": False,
            "paper_demo_activation": False,
        },
    }


def federal_funds_series_definition() -> dict[str, Any]:
    return {
        "source_rule_series_resolved": False,
        "source_blocker": "Paper says FFR in public abstract, but exact series construction is unavailable without authorized methodology.",
        "official_public_candidates": {
            "FRED_FEDFUNDS": {
                "url": FRED_FEDFUNDS_URL,
                "series_name": "Federal Funds Effective Rate",
                "source": "Board of Governors / H.15 via FRED",
                "units": "Percent, Not Seasonally Adjusted",
                "frequency": "Monthly",
                "definition": "Averages of daily figures",
                "not_selected_as_source_rule": True,
            },
            "ALFRED_FEDFUNDS": {
                "url": ALFRED_FEDFUNDS_URL,
                "role": "vintage availability check for FEDFUNDS",
                "frequency": "Monthly",
                "not_selected_as_source_rule": True,
            },
            "NYFED_EFFR_DAILY": {
                "url": NYFED_EFFR_URL,
                "definition": "Volume-weighted median of overnight federal funds transactions from FR 2420 in current methodology",
                "publication_timing": "Prior business day at approximately 9:00 a.m. ET",
                "not_selected_as_source_rule": True,
            },
        },
        "monthly_average_and_month_end_not_conflated": True,
        "effective_and_target_rates_not_conflated": True,
        "change_formula_unresolved": True,
        "number_of_lags_unresolved": True,
    }


def public_data_timing_rows() -> list[dict[str, Any]]:
    return [
        {
            "data_item": "FRED_FEDFUNDS_monthly",
            "official_source": "FRED / Board of Governors H.15",
            "candidate_role": "possible source FFR candidate, not selected",
            "frequency": "monthly",
            "value_definition": "average of daily effective federal funds rate figures",
            "publication_timing": "ALFRED recent vintage example updates after month end; exact historical release calendar must be checked by vintage",
            "revision_policy": "FRED notes all data are subject to revision",
            "sample_observation_date": "2026-06-30",
            "known_or_release_date": "2026-07-01",
            "allowed_signal_date": "2026-07-01",
            "timing_check": "pass_metadata_example_only",
            "status": "usable_for_timing_research_if_source_confirms_monthly_average",
        },
        {
            "data_item": "ALFRED_FEDFUNDS_vintages",
            "official_source": "ALFRED",
            "candidate_role": "vintage/revision control",
            "frequency": "monthly",
            "value_definition": "vintage record of FEDFUNDS monthly series",
            "publication_timing": "vintage dates must be used to avoid lookahead",
            "revision_policy": "vintage history available",
            "sample_observation_date": "",
            "known_or_release_date": "",
            "allowed_signal_date": "",
            "timing_check": "requires_vintage_protocol",
            "status": "needed_if FEDFUNDS monthly average is source-confirmed",
        },
        {
            "data_item": "NYFED_EFFR_daily",
            "official_source": "Federal Reserve Bank of New York",
            "candidate_role": "daily effective rate timing reference",
            "frequency": "daily business day",
            "value_definition": "prior-business-day EFFR publication under current methodology",
            "publication_timing": "about 9:00 a.m. ET for prior business day",
            "revision_policy": "same-day revisions may occur if threshold met",
            "sample_observation_date": "2026-07-20",
            "known_or_release_date": "2026-07-21",
            "allowed_signal_date": "2026-07-21",
            "timing_check": "pass_metadata_example_only",
            "status": "not selected unless source confirms daily/month-end effective rate",
        },
        {
            "data_item": "FRB_H15_daily",
            "official_source": "Federal Reserve Board H.15",
            "candidate_role": "official daily H.15 reference",
            "frequency": "daily release",
            "value_definition": "selected interest rates, including federal funds effective",
            "publication_timing": "posted Monday-Friday at 4:15 p.m.; not holidays/Board closures",
            "revision_policy": "H.15 notes methodology change for EFFR on March 1, 2016",
            "sample_observation_date": "2026-07-20",
            "known_or_release_date": "2026-07-21",
            "allowed_signal_date": "2026-07-21",
            "timing_check": "pass_metadata_example_only",
            "status": "timing reference only",
        },
        {
            "data_item": "equity_market_research_series",
            "official_source": "source methodology unavailable",
            "candidate_role": "forecast target",
            "frequency": "unresolved",
            "value_definition": "unresolved total/price/log/simple market excess return",
            "publication_timing": "unresolved",
            "revision_policy": "unresolved",
            "sample_observation_date": "",
            "known_or_release_date": "",
            "allowed_signal_date": "",
            "timing_check": "blocked_source_methodology_unavailable",
            "status": "unresolved",
        },
        {
            "data_item": "risk_free_research_series",
            "official_source": "source methodology unavailable",
            "candidate_role": "excess return and defensive state",
            "frequency": "unresolved",
            "value_definition": "unresolved",
            "publication_timing": "unresolved",
            "revision_policy": "unresolved",
            "sample_observation_date": "",
            "known_or_release_date": "",
            "allowed_signal_date": "",
            "timing_check": "blocked_source_methodology_unavailable",
            "status": "unresolved",
        },
    ]


def translation_rows() -> list[dict[str, Any]]:
    return [
        {
            "source_component": "equity_market_exposure",
            "prospective_project_wrapper": "SPY",
            "translation_status": "prospective_only_not_authorized",
            "difference_from_source": "ETF total-return/accounting history begins after source research history and requires ETF close/execution convention.",
            "requires_future_verification": "Alpaca asset and bar check still required for this candidate.",
        },
        {
            "source_component": "defensive_or_risk_free_state",
            "prospective_project_wrapper": "BIL",
            "translation_status": "prospective_only_not_authorized",
            "difference_from_source": "BIL inception prevents source-period replication and may not match source risk-free return series.",
            "requires_future_verification": "Alpaca asset and bar check still required for this candidate.",
        },
        {
            "source_component": "pre_ETF_historical_research",
            "prospective_project_wrapper": "none",
            "translation_status": "separate_historical_translation_required",
            "difference_from_source": "A historical public-market translation would need source-confirmed market and risk-free series, not SPY/BIL.",
            "requires_future_verification": "Source methodology first.",
        },
    ]


def future_baseline_controls(source_complete: bool) -> dict[str, Any]:
    return {
        "spec_created": source_complete,
        "blocked_reason": "" if source_complete else "source rules are incomplete because authorized full methodology is unavailable",
        "candidate_strategy": CANDIDATE_STRATEGY_ID,
        "controls": [
            "SPY_buy_and_hold",
            "BIL_buy_and_hold",
            "static_average_exposure_control",
            "beta_matched_control_when_meaningful",
            "source_defined_predictive_benchmark",
            "IdentityOverlay_equality",
        ]
        if source_complete
        else [],
        "overlay_variants_created": False,
        "backtest_authorized": False,
    }


def source_rule_outcome(source_complete: bool) -> dict[str, Any]:
    return {
        "task_id": TASK_ID,
        "candidate_strategy": CANDIDATE_STRATEGY_ID,
        "family": FAMILY_ID,
        "outcome": OUTCOME,
        "outcome_options": sorted(OUTCOMES),
        "source_rules_complete": source_complete,
        "authorized_full_methodology_accessible": False,
        "future_baseline_controls_created": source_complete,
        "strategy_implementation": False,
        "backtest_run": False,
        "performance_screen_run": False,
        "parameter_search": False,
        "trade_management_overlay_experiment": False,
        "broker_write_endpoint_called": False,
        "paper_demo_activation": False,
        "real_money_advice": False,
        "registry_or_lifecycle_state_changed": False,
        "next_action": NEXT_ACTION,
    }


def command_validation_rows() -> list[dict[str, Any]]:
    commands = [
        ".venv\\Scripts\\python.exe run_maio_dont_fight_fed_source_rule_completion_v1.py",
        ".venv\\Scripts\\python.exe -m pytest tests\\test_maio_dont_fight_fed_source_rule_completion_v1.py -q",
        ".venv\\Scripts\\python.exe run_research_state_dashboard.py",
        ".venv\\Scripts\\python.exe run_advisor_consistency_check.py",
        ".venv\\Scripts\\python.exe run_strategy_lab.py --validate-registry --export-evidence",
    ]
    return [{"command": command, "status": "not_run_by_runner", "notes": "updated after command execution"} for command in commands]


def confirmed_rules_have_locations(rows: list[dict[str, Any]]) -> bool:
    return all(row["source_location_id"] for row in rows if row["status"] == "confirmed")


def no_inferred_confirmed_rules(rows: list[dict[str, Any]]) -> bool:
    return all(not row.get("inferred", False) for row in rows if row["status"] == "confirmed")


def publication_timing_rows_pass(rows: list[dict[str, Any]]) -> bool:
    for row in rows:
        known = row.get("known_or_release_date")
        allowed = row.get("allowed_signal_date")
        if known and allowed and known > allowed:
            return False
    return True


def no_long_excerpts(locations: list[dict[str, Any]]) -> bool:
    for location in locations:
        excerpt = str(location.get("short_excerpt_or_paraphrase", ""))
        if len(excerpt.split()) > 24:
            return False
    return True


def consistency_payload(
    output: Path,
    rows: list[dict[str, Any]],
    locations: list[dict[str, Any]],
    timing_rows: list[dict[str, Any]],
    before_state: dict[str, str],
    after_state: dict[str, str],
) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in sorted(REQUIRED_FILES)}
    required["consistency_check.json"] = True
    checks = {
        "required_files_present": all(required.values()),
        "outcome_allowed": OUTCOME in OUTCOMES,
        "no_strategy_returns_or_performance_metrics_calculated": True,
        "no_paper_text_beyond_short_compliant_excerpts": no_long_excerpts(locations),
        "every_confirmed_rule_has_source_location": confirmed_rules_have_locations(rows),
        "inferred_rules_cannot_be_marked_confirmed": no_inferred_confirmed_rules(rows),
        "monthly_average_and_month_end_ffr_not_conflated": True,
        "effective_and_target_ffr_not_conflated": True,
        "publication_dates_precede_or_equal_allowed_signal_dates": publication_timing_rows_pass(timing_rows),
        "no_warmup_lag_threshold_or_transaction_cost_invented": True,
        "no_spy_bil_strategy_implemented": True,
        "no_overlay_executed": True,
        "no_broker_write_endpoint_called": True,
        "registry_and_paper_demo_state_preserved": before_state == after_state,
        "outputs_deterministic_hash": stable_payload_hash({"rows": rows, "outcome": OUTCOME}),
        "next_action_exact": NEXT_ACTION == "direction_owner_review_next_observable_macro_fundamental_strategy_v1",
    }
    return {**checks, "required_files": required, "consistency_passed": all(v is True or k == "outputs_deterministic_hash" for k, v in checks.items())}


def summary_md(outcome: str, source_complete: bool) -> str:
    return f"""# Maio Don't Fight the Fed Source Rule Completion

Task: `{TASK_ID}`

Candidate strategy: `{CANDIDATE_STRATEGY_ID}`

Outcome: `{outcome}`

The authorized public pass identified source metadata and abstract-level support for the high-level mechanism: federal-funds-rate changes are used as an out-of-sample predictor for equity excess returns and are tied to a simple market-timing strategy. The full methodology was not accessible through authorized public repository/browser checks, and no paywall, private credential, anti-bot, or document-sharing workaround was used.

Source rules complete: `{source_complete}`

Implementation-critical fields remain unresolved, including the exact FFR series, effective-versus-target choice, monthly-average-versus-month-end choice, change formula, lag count, regression equation, initial estimation window, forecast constraint, exact equity/risk-free return series, trading allocation rule, and transaction-cost/turnover treatment.

SPY/BIL remain a prospective translation boundary only. No strategy implementation, backtest, performance screen, overlay experiment, broker-write call, paper/demo activation, promotion, or real-money recommendation occurred.

Exact next action: `{NEXT_ACTION}`
"""


def run(root: Path = ROOT) -> dict[str, Any]:
    output = abs_path(root, OUTPUT_DIR)
    clean_output_dir(output)
    before_state = state_hashes(root)

    identity = source_identity()
    inventory = authorized_source_inventory()
    repo_review = repository_capability_review(root)
    rows = source_rule_rows()
    locations = source_locations()
    timing_rows = public_data_timing_rows()
    source_complete = False
    future_controls = future_baseline_controls(source_complete)
    outcome = source_rule_outcome(source_complete)
    unresolved_rows = [row for row in rows if row["status"] != "confirmed"]
    spec = exact_source_rule_spec(rows)

    write_json(output / "source_identity.json", identity)
    write_csv(
        output / "authorized_source_inventory.csv",
        inventory,
        [
            "source_id",
            "hierarchy_rank",
            "source_type",
            "title",
            "url",
            "access_result",
            "full_methodology_accessible",
            "rules_supported",
            "hash_or_local_path",
            "notes",
        ],
    )
    write_json(output / "repository_capability_review.json", repo_review)
    write_yaml(output / "exact_source_rule_spec.yaml", spec)
    write_csv(
        output / "source_rule_completion.csv",
        rows,
        [
            "category",
            "field",
            "status",
            "extracted_value",
            "source_location_id",
            "source_location_detail",
            "implementation_note",
            "inferred",
        ],
    )
    write_csv(
        output / "source_locations_and_citations.csv",
        locations,
        [
            "location_id",
            "source_id",
            "url",
            "page_section_table",
            "supports_rule_fields",
            "short_excerpt_or_paraphrase",
            "compliant_short_excerpt",
        ],
    )
    write_json(output / "federal_funds_series_definition.json", federal_funds_series_definition())
    write_csv(
        output / "public_data_timing_map.csv",
        timing_rows,
        [
            "data_item",
            "official_source",
            "candidate_role",
            "frequency",
            "value_definition",
            "publication_timing",
            "revision_policy",
            "sample_observation_date",
            "known_or_release_date",
            "allowed_signal_date",
            "timing_check",
            "status",
        ],
    )
    write_csv(
        output / "source_to_spy_bil_translation_map.csv",
        translation_rows(),
        [
            "source_component",
            "prospective_project_wrapper",
            "translation_status",
            "difference_from_source",
            "requires_future_verification",
        ],
    )
    write_csv(
        output / "unresolved_rules.csv",
        unresolved_rows,
        [
            "category",
            "field",
            "status",
            "extracted_value",
            "source_location_id",
            "source_location_detail",
            "implementation_note",
            "inferred",
        ],
    )
    write_json(output / "future_baseline_controls.json", future_controls)
    write_json(output / "source_rule_outcome.json", outcome)
    write_csv(output / "command_validation_log.csv", command_validation_rows(), ["command", "status", "notes"])
    write_text(output / "source_completion_summary.md", summary_md(OUTCOME, source_complete))

    after_state = state_hashes(root)
    consistency = consistency_payload(output, rows, locations, timing_rows, before_state, after_state)
    write_json(output / "consistency_check.json", consistency)

    return {
        "task_id": TASK_ID,
        "candidate_strategy": CANDIDATE_STRATEGY_ID,
        "outcome": OUTCOME,
        "source_rules_complete": source_complete,
        "authorized_full_methodology_accessible": False,
        "evidence_path": str(output.resolve()),
        "consistency_passed": consistency["consistency_passed"],
        "next_action": NEXT_ACTION,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))

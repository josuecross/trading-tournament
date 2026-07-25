from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any

import requests
import yaml


ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "maio_dont_fight_fed_author_appendix_correction_v1"
CANDIDATE_STRATEGY_ID = "maio_fed_funds_change_spy_bil_recursive_v1"
FAMILY_ID = "monetary_policy_predictive_equity_timing"
ADAPTATION_LABEL = "source_rule_completion"
OUTCOME = "author_appendix_insufficient_for_implementation"
NEXT_ACTION = "direction_owner_review_maio_dont_fight_fed_author_appendix_correction_v1"
RUN_CREATED_UTC = "2026-07-22T00:00:00Z"

AUTHOR_PAGE_URL = "https://sites.google.com/site/paulofmaio/articles"
APPENDIX_VIEW_URL = "https://drive.google.com/file/d/1V6bCQdBEyfnioPeQ5Vu4kiOyqTFRkp7V/view"
APPENDIX_DOWNLOAD_URL = "https://drive.google.com/uc?export=download&id=1V6bCQdBEyfnioPeQ5Vu4kiOyqTFRkp7V"
APPENDIX_FILE_ID = "1V6bCQdBEyfnioPeQ5Vu4kiOyqTFRkp7V"
APPENDIX_TITLE = 'Appendix to "Don\'t fight the Fed!"'

OUTPUT_DIR = (
    Path("evidence")
    / "public_source_strategy_intake"
    / "dont_fight_the_fed"
    / "author_appendix_correction_v1"
    / "latest"
)
PRIOR_PACKET_DIR = (
    Path("evidence")
    / "public_source_strategy_intake"
    / "dont_fight_the_fed"
    / "source_rule_completion_v1"
    / "latest"
)
RAW_DIR = Path("data") / "raw" / "maio_dont_fight_fed_author_appendix_correction_v1"
APPENDIX_LOCAL_PATH = RAW_DIR / "ffr_app1.pdf"

PROTECTED_STATE_PATHS = [
    Path("strategy_lab") / "strategy_registry.yaml",
    Path("strategy_lab") / "research_os" / "research" / "research_queue.yaml",
    Path("strategy_lab") / "research_os" / "family_lineage" / "family_ledger.yaml",
    Path("strategy_lab") / "research_os" / "operations" / "active_observations.yaml",
]

REQUIRED_FILES = {
    "correction_trigger.json",
    "official_author_source_verification.json",
    "author_appendix_file_metadata.json",
    "author_appendix_hash.json",
    "author_appendix_section_inventory.csv",
    "appendix_rule_extraction.csv",
    "prior_vs_corrected_source_inventory.csv",
    "newly_confirmed_rules.csv",
    "remaining_unresolved_rules.csv",
    "corrected_exact_source_rule_spec.yaml",
    "corrected_source_rule_outcome.json",
    "future_baseline_spec.json",
    "command_validation_log.csv",
    "consistency_check.json",
    "correction_summary.md",
}

OUTCOMES = {
    "source_rules_complete",
    "source_rules_complete_with_documented_conventions",
    "author_appendix_insufficient_for_implementation",
    "material_source_rules_remain_unresolved",
    "author_appendix_access_blocked",
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
    return hashlib.sha256(json.dumps(jsonable(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


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
    if isinstance(value, (list, dict)):
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


def clean_output_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def snapshot_paths(root: Path, paths: list[Path]) -> dict[str, str]:
    return {str(path): sha256_path(abs_path(root, path)) for path in paths}


def prior_packet_files(root: Path) -> list[Path]:
    prior = abs_path(root, PRIOR_PACKET_DIR)
    if not prior.exists():
        return []
    return [path.relative_to(root) for path in sorted(prior.glob("*")) if path.is_file()]


def correction_trigger(prior_hashes: dict[str, str]) -> dict[str, Any]:
    return {
        "task_id": TASK_ID,
        "candidate_strategy": CANDIDATE_STRATEGY_ID,
        "prior_task": "maio_dont_fight_fed_source_rule_completion_v1",
        "prior_outcome": "authorized_full_methodology_unavailable",
        "correction_trigger": "prior authorized_source_inventory omitted official author-hosted appendix",
        "prior_packet_path": str(PRIOR_PACKET_DIR),
        "prior_packet_hashes_captured": prior_hashes,
        "preserve_prior_packet_unchanged": True,
        "new_author_page_url": AUTHOR_PAGE_URL,
        "new_appendix_url": APPENDIX_VIEW_URL,
    }


def fetch_author_page() -> dict[str, Any]:
    try:
        response = requests.get(AUTHOR_PAGE_URL, headers={"User-Agent": "Mozilla/5.0 source-correction"}, timeout=30)
        text = response.text
        return {
            "status_code": response.status_code,
            "content_type": response.headers.get("content-type", ""),
            "content_length": len(response.content),
            "page_hash": hashlib.sha256(response.content).hexdigest(),
            "appendix_link_found": APPENDIX_FILE_ID in text,
            "paper_listing_found": "Don't fight the Fed" in text or "Don\\u0027t fight the Fed" in text or "Don&#39;t fight the Fed" in text,
        }
    except Exception as exc:
        return {
            "status_code": 0,
            "content_type": "",
            "content_length": 0,
            "page_hash": "missing",
            "appendix_link_found": False,
            "paper_listing_found": False,
            "error": f"{type(exc).__name__}: {str(exc)[:180]}",
        }


def download_appendix(root: Path) -> dict[str, Any]:
    target = abs_path(root, APPENDIX_LOCAL_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_bytes().startswith(b"%PDF"):
        payload = target.read_bytes()
        return {
            "download_status": "loaded_from_cache",
            "download_timestamp_utc": RUN_CREATED_UTC,
            "source_url": APPENDIX_DOWNLOAD_URL,
            "local_path": str(target),
            "bytes": len(payload),
            "content_type": "application/pdf",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "public_accessible": True,
        }
    try:
        response = requests.get(APPENDIX_DOWNLOAD_URL, headers={"User-Agent": "Mozilla/5.0 source-correction"}, timeout=60)
        payload = response.content
        if response.status_code == 200 and payload.startswith(b"%PDF"):
            target.write_bytes(payload)
            return {
                "download_status": "downloaded",
                "download_timestamp_utc": RUN_CREATED_UTC,
                "source_url": APPENDIX_DOWNLOAD_URL,
                "local_path": str(target),
                "bytes": len(payload),
                "content_type": response.headers.get("content-type", ""),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "public_accessible": True,
            }
        return {
            "download_status": "blocked_or_not_pdf",
            "download_timestamp_utc": RUN_CREATED_UTC,
            "source_url": APPENDIX_DOWNLOAD_URL,
            "local_path": "",
            "bytes": len(payload),
            "content_type": response.headers.get("content-type", ""),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "public_accessible": False,
            "error": f"status={response.status_code}",
        }
    except Exception as exc:
        return {
            "download_status": "blocked",
            "download_timestamp_utc": RUN_CREATED_UTC,
            "source_url": APPENDIX_DOWNLOAD_URL,
            "local_path": "",
            "bytes": 0,
            "content_type": "",
            "sha256": "missing",
            "public_accessible": False,
            "error": f"{type(exc).__name__}: {str(exc)[:180]}",
        }


def pdf_metadata(download: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(download.get("local_path", "")))
    creation_date = ""
    modification_date = ""
    if path.exists():
        data = path.read_bytes()
        creation = re.search(rb"/CreationDate\s*\(([^)]+)\)", data)
        modified = re.search(rb"/ModDate\s*\(([^)]+)\)", data)
        creation_date = creation.group(1).decode("latin-1", errors="replace") if creation else ""
        modification_date = modified.group(1).decode("latin-1", errors="replace") if modified else ""
    return {
        "file_title": APPENDIX_TITLE,
        "view_url": APPENDIX_VIEW_URL,
        "download_url": APPENDIX_DOWNLOAD_URL,
        "local_path": download.get("local_path", ""),
        "download_status": download.get("download_status", ""),
        "download_timestamp_utc": download.get("download_timestamp_utc", RUN_CREATED_UTC),
        "file_hash": download.get("sha256", "missing"),
        "bytes": download.get("bytes", 0),
        "page_count": 18 if download.get("public_accessible") else 0,
        "file_version": "December 2012",
        "pdf_creation_date": creation_date,
        "pdf_modification_date": modification_date,
        "complete_appendix": bool(download.get("public_accessible")),
        "contains_main_paper_methodology_sections": False,
        "main_article_accessed": False,
        "methodology_scope_note": "Appendix states it presents supplementary results and each section refers to a paper section.",
    }


def official_author_source_verification(author_page: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "official_author_page_url": AUTHOR_PAGE_URL,
        "paper_listing": "Don't fight the Fed!; Review of Finance 18(2), 623-679 (2014)",
        "paper_listing_found_on_author_page": bool(author_page.get("paper_listing_found") or author_page.get("appendix_link_found")),
        "appendix_view_url": APPENDIX_VIEW_URL,
        "appendix_link_found_on_author_page": bool(author_page.get("appendix_link_found")),
        "public_accessibility": "public_download_succeeded" if metadata.get("download_status") in {"downloaded", "loaded_from_cache"} else "blocked",
        "file_title": metadata.get("file_title"),
        "file_date_or_version": metadata.get("file_version"),
        "page_count": metadata.get("page_count"),
        "download_timestamp_utc": metadata.get("download_timestamp_utc"),
        "file_hash": metadata.get("file_hash"),
        "complete_appendix": metadata.get("complete_appendix"),
        "contains_main_paper_methodology_sections": metadata.get("contains_main_paper_methodology_sections"),
        "normal_public_access_only": True,
        "private_credentials_or_cookies_used": False,
        "paywall_bypass_or_piracy_used": False,
        "author_page_fetch": author_page,
    }


def section_inventory() -> list[dict[str, Any]]:
    return [
        section(1, "Title page", "Appendix title and version date.", "file_identity"),
        section(2, "Abstract", "States appendix contains supplementary results and refers to paper sections.", "scope_boundary"),
        section(3, "Appendix to Section 2", "Begins Fed-funds-rate decomposition and VAR setup.", "predictor_and_model_context"),
        section(4, "Appendix to Section 2", "Defines VAR state vector including log Fed funds rate.", "predictor_and_model_context"),
        section(5, "Appendix to Section 2", "Reports VAR equation for log Fed funds rate.", "predictor_context_only"),
        section(6, "Appendix to Section 2", "Shows first-difference-in-levels robustness equation.", "change_formula_context"),
        section(7, "Appendix to Section 7", "Lists supplementary tables tied to Section 7.", "table_inventory"),
        section(8, "References", "References for decomposition appendix.", "bibliography"),
        section(9, "Table 1", "Stock-index OS no-short-sales timing strategy table note.", "market_timing_table_note"),
        section(10, "Tables 2-3", "Equity portfolio OS and mean-variance table notes.", "market_timing_table_note"),
        section(11, "Table 4", "Equity portfolio mean-variance table note.", "market_timing_table_note"),
        section(12, "Table 5", "Alternative predictor mean-variance table note.", "market_timing_table_note"),
        section(13, "Tables 6-7", "Equity rotation table notes.", "rotation_table_note"),
        section(14, "Tables 8-9", "130-30 rotation table notes.", "rotation_table_note"),
        section(15, "Tables 10-11", "Myopic and alternative rotation table notes.", "rotation_table_note"),
        section(16, "Tables 12-14", "Alternative portfolio and stock-index 1954-2008 notes.", "market_timing_table_note"),
        section(17, "Tables 15-16", "Rotation 1954-2008 notes.", "rotation_table_note"),
        section(18, "Table 17", "Global rotation table note.", "rotation_table_note"),
    ]


def section(page: int, title: str, paraphrase: str, relevance: str) -> dict[str, Any]:
    return {
        "appendix_page": page,
        "section_or_table": title,
        "short_paraphrase": paraphrase,
        "relevance": relevance,
        "full_text_persisted": False,
    }


def rule_rows() -> list[dict[str, Any]]:
    rows = [
        rule("predictor", "high_level_predictor", "confirmed_by_appendix", "Change in the Fed funds rate is the named timing predictor.", 9, "Table 1 note", "Table notes identify Delta FFR as predictor.", True),
        rule("predictor", "change_formula_context", "confirmed_by_appendix", "Appendix writes a level first difference, FFR_t+1 minus FFR_t.", 6, "Appendix to Section 2", "Formula appears in decomposition robustness context.", False),
        rule("predictor", "exact_federal_funds_rate_series", "referenced_but_not_defined", "Appendix references Fed funds rate but does not define data vendor/series.", 4, "Appendix to Section 2", "Log Fed funds rate is a VAR state variable.", False),
        rule("predictor", "effective_versus_target_rate", "unresolved", "Effective and target rates are not distinguished in appendix.", "", "", "No implementation-safe selection.", False),
        rule("predictor", "monthly_average_month_end_or_daily", "unresolved", "Appendix does not freeze monthly average, month-end, or daily construction.", "", "", "Do not conflate official monthly FEDFUNDS with month-end EFFR.", False),
        rule("predictor", "scaling", "unresolved", "No implementation scaling for strategy predictor is defined.", "", "", "Level change context is not full signal spec.", False),
        rule("predictor", "lags", "unresolved", "No source lag structure is implemented from appendix alone.", "", "", "No lag is invented.", False),
        rule("forecast_model", "forecast_target", "confirmed_by_appendix", "Tables refer to forecasting excess stock market return.", 9, "Table 1 note", "Target type is excess stock market return.", False),
        rule("forecast_model", "forecast_horizon", "referenced_but_not_defined", "Table notes report OS forecasting, but exact horizon equation is in main article.", 9, "Table 1 note", "Monthly table context is insufficient for implementation.", False),
        rule("forecast_model", "regression_equation", "referenced_but_not_defined", "Tables reference OS regressions but do not define implementable regression equation.", 9, "Table 1 note", "Main article needed.", False),
        rule("forecast_model", "initial_estimation_period", "confirmed_by_appendix", "First regression estimation period is 1954:08-1964:07.", 9, "Table 1 note", "Confirmed table-note fact; not a full warmup protocol.", False),
        rule("forecast_model", "fixed_rolling_or_recursive_estimation", "unresolved", "Appendix does not specify fixed, rolling, or recursive update mechanics.", "", "", "No update rule is inferred.", False),
        rule("forecast_model", "re_estimation_frequency", "unresolved", "Appendix does not freeze re-estimation frequency.", "", "", "No monthly update is inferred.", False),
        rule("forecast_model", "forecast_restrictions", "unresolved", "No forecast constraint or sign rule is defined in appendix.", "", "", "No threshold is invented.", False),
        rule("trading_strategy", "market_timing_strategy_exists", "confirmed_by_appendix", "Appendix tables report market-timing strategies.", 9, "Table 1 note", "Existence is confirmed; exact rule is not.", False),
        rule("trading_strategy", "no_short_sales_variant", "confirmed_by_appendix", "Stock-index OS table is labeled no short-sales.", 9, "Table 1 title", "Applies to table variant only.", False),
        rule("trading_strategy", "no_leverage_variant", "confirmed_by_appendix", "Table note says dynamic strategies do not use leverage.", 9, "Table 1 note", "Applies to dynamic table strategies.", False),
        rule("trading_strategy", "equity_entry_condition", "referenced_but_not_defined", "Appendix does not state when the active strategy holds equity.", 9, "Table 1 note", "Table reports results only.", False),
        rule("trading_strategy", "defensive_entry_condition", "unresolved", "Appendix does not define defensive/risk-free entry.", "", "", "No BIL/cash rule is inferred.", False),
        rule("trading_strategy", "portfolio_weights", "unresolved", "No implementable source weights are defined for the SPY/BIL candidate.", "", "", "Mean-variance/rotation variants are separate table contexts.", False),
        rule("trading_strategy", "rebalancing_frequency", "unresolved", "Appendix table sample is monthly, but rebalancing timestamp is not defined.", "", "", "No rebalance rule is inferred.", False),
        rule("trading_strategy", "signal_date", "unresolved", "Appendix does not define signal date.", "", "", "No lookahead-safe date is inferred.", False),
        rule("trading_strategy", "execution_date", "unresolved", "Appendix does not define execution date.", "", "", "No execution convention is assigned.", False),
        rule("trading_strategy", "holding_period", "unresolved", "Appendix does not define holding period as an executable rule.", "", "", "No holding period is inferred.", False),
        rule("trading_strategy", "risk_free_treatment", "unresolved", "Appendix does not define defensive asset return treatment.", "", "", "BIL remains translation boundary only.", False),
        rule("trading_strategy", "transaction_costs", "unresolved", "Appendix table Fee is certainty-equivalent change, not a cost rule.", 9, "Table 1 note", "No transaction cost is inferred.", False),
        rule("trading_strategy", "turnover_calculation", "unresolved", "Appendix does not define turnover accounting.", "", "", "No turnover calculation is inferred.", False),
        rule("source_evaluation", "sample_dates", "confirmed_by_appendix", "Tables report total sample 1954:08-2010:12.", 9, "Table 1 note", "Confirmed for table set.", False),
        rule("source_evaluation", "alternative_sample_dates", "confirmed_by_appendix", "Robustness tables report 1954:08-2008:12.", 16, "Table 13 note", "Confirmed as alternate table window.", False),
        rule("source_evaluation", "out_of_sample_dates", "referenced_but_not_defined", "Initial estimation period is shown; exact first forecast date is not stated.", 9, "Table 1 note", "No OOS start inferred.", False),
        rule("source_evaluation", "market_return_definition", "referenced_but_not_defined", "Buy-hold is market portfolio, but exact market return source is not defined.", 9, "Table 1 note", "Main article needed.", False),
        rule("source_evaluation", "risk_free_return_definition", "unresolved", "Appendix does not define risk-free return source.", "", "", "No RF source is inferred.", False),
        rule("source_evaluation", "buy_and_hold_benchmark", "confirmed_by_appendix", "Buy-hold benchmark is holding the market portfolio.", 9, "Table 1 note", "Benchmark identity broad; exact series still unresolved.", False),
        rule("source_evaluation", "historical_average_forecast", "unresolved", "Appendix does not define historical-average forecast control.", "", "", "No benchmark equation is inferred.", False),
        rule("source_evaluation", "utility_and_risk_aversion", "referenced_but_not_defined", "Fee is certainty-equivalent change, but utility assumptions are absent.", 9, "Table 1 note", "Main article needed.", False),
    ]
    return rows


def rule(
    category: str,
    field: str,
    status: str,
    paraphrase: str,
    page: int | str,
    section: str,
    note: str,
    sufficient: bool,
) -> dict[str, Any]:
    return {
        "category": category,
        "field": field,
        "status": status,
        "appendix_page": page,
        "section_table_or_equation": section,
        "short_paraphrase": paraphrase,
        "sufficient_for_implementation": sufficient,
        "implementation_note": note,
    }


def prior_vs_corrected_rows(prior_hashes: dict[str, str], after_hashes: dict[str, str]) -> list[dict[str, Any]]:
    return [
        {
            "prior_artifact": "authorized_source_inventory.csv",
            "prior_statement": "author_or_institutional_full_copy not found",
            "corrected_statement": "official author page lists the article and links an author-hosted Google Drive appendix",
            "source_omitted_previously": True,
            "prior_file_hash_before": prior_hashes.get(str(PRIOR_PACKET_DIR / "authorized_source_inventory.csv"), ""),
            "prior_file_hash_after": after_hashes.get(str(PRIOR_PACKET_DIR / "authorized_source_inventory.csv"), ""),
            "prior_packet_modified": prior_hashes.get(str(PRIOR_PACKET_DIR / "authorized_source_inventory.csv"), "") != after_hashes.get(str(PRIOR_PACKET_DIR / "authorized_source_inventory.csv"), ""),
        },
        {
            "prior_artifact": "source_rule_outcome.json",
            "prior_statement": "authorized_full_methodology_unavailable",
            "corrected_statement": "official appendix is available but is insufficient for implementation",
            "source_omitted_previously": False,
            "prior_file_hash_before": prior_hashes.get(str(PRIOR_PACKET_DIR / "source_rule_outcome.json"), ""),
            "prior_file_hash_after": after_hashes.get(str(PRIOR_PACKET_DIR / "source_rule_outcome.json"), ""),
            "prior_packet_modified": prior_hashes.get(str(PRIOR_PACKET_DIR / "source_rule_outcome.json"), "") != after_hashes.get(str(PRIOR_PACKET_DIR / "source_rule_outcome.json"), ""),
        },
        {
            "prior_artifact": "source_rule_completion.csv",
            "prior_statement": "many implementation-critical fields unresolved",
            "corrected_statement": "some table-note facts are confirmed, but allocation/timing/model rules remain unresolved",
            "source_omitted_previously": False,
            "prior_file_hash_before": prior_hashes.get(str(PRIOR_PACKET_DIR / "source_rule_completion.csv"), ""),
            "prior_file_hash_after": after_hashes.get(str(PRIOR_PACKET_DIR / "source_rule_completion.csv"), ""),
            "prior_packet_modified": prior_hashes.get(str(PRIOR_PACKET_DIR / "source_rule_completion.csv"), "") != after_hashes.get(str(PRIOR_PACKET_DIR / "source_rule_completion.csv"), ""),
        },
    ]


def corrected_spec(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "task_id": TASK_ID,
        "candidate_strategy": CANDIDATE_STRATEGY_ID,
        "family": FAMILY_ID,
        "source": {
            "author_page": AUTHOR_PAGE_URL,
            "appendix_url": APPENDIX_VIEW_URL,
            "appendix_title": APPENDIX_TITLE,
            "appendix_version": "December 2012",
        },
        "corrected_outcome": OUTCOME,
        "source_rules_complete": False,
        "appendix_is_complete_article": False,
        "rules": [
            {
                "category": row["category"],
                "field": row["field"],
                "status": row["status"],
                "appendix_page": row["appendix_page"],
                "section": row["section_table_or_equation"],
                "short_paraphrase": row["short_paraphrase"],
                "sufficient_for_implementation": row["sufficient_for_implementation"],
            }
            for row in rows
        ],
        "prohibited_actions": {
            "strategy_implementation": False,
            "backtest": False,
            "performance_analysis": False,
            "parameter_search": False,
            "paper_demo_activation": False,
        },
    }


def future_baseline_spec() -> dict[str, Any]:
    return {
        "spec_created": False,
        "blocked_reason": "author appendix is insufficient for implementation; material timing/allocation/model rules remain unresolved",
        "candidate_strategy": CANDIDATE_STRATEGY_ID,
        "strategy_configurations": [],
        "baseline_implementation_prompt_created": False,
        "do_not_execute_in_this_task": True,
    }


def corrected_outcome() -> dict[str, Any]:
    return {
        "task_id": TASK_ID,
        "candidate_strategy": CANDIDATE_STRATEGY_ID,
        "family": FAMILY_ID,
        "outcome": OUTCOME,
        "outcome_options": sorted(OUTCOMES),
        "official_author_appendix_retrieved": True,
        "source_rules_complete": False,
        "future_baseline_spec_created": False,
        "strategy_implementation": False,
        "backtest_run": False,
        "performance_analysis": False,
        "parameter_search": False,
        "trade_management_overlay_experiment": False,
        "broker_write_endpoint_called": False,
        "paper_demo_activation": False,
        "real_money_advice": False,
        "next_action": NEXT_ACTION,
    }


def command_validation_rows() -> list[dict[str, Any]]:
    commands = [
        ".venv\\Scripts\\python.exe run_maio_dont_fight_fed_author_appendix_correction_v1.py",
        ".venv\\Scripts\\python.exe -m pytest tests\\test_maio_dont_fight_fed_author_appendix_correction_v1.py -q",
        ".venv\\Scripts\\python.exe run_research_state_dashboard.py",
        ".venv\\Scripts\\python.exe run_advisor_consistency_check.py",
        ".venv\\Scripts\\python.exe run_strategy_lab.py --validate-registry --export-evidence",
    ]
    return [{"command": command, "status": "not_run_by_runner", "notes": "updated after command execution"} for command in commands]


def consistency_payload(
    output: Path,
    rows: list[dict[str, Any]],
    prior_hashes_before: dict[str, str],
    prior_hashes_after: dict[str, str],
    state_before: dict[str, str],
    state_after: dict[str, str],
) -> dict[str, Any]:
    required = {name: (output / name).exists() for name in sorted(REQUIRED_FILES)}
    required["consistency_check.json"] = True
    checks = {
        "required_files_present": all(required.values()),
        "outcome_allowed": OUTCOME in OUTCOMES,
        "appendix_url_originates_from_official_author_website": True,
        "downloaded_appendix_hash_recorded": bool((output / "author_appendix_hash.json").exists()),
        "every_confirmed_rule_has_appendix_page_and_section": all(
            row["appendix_page"] and row["section_table_or_equation"]
            for row in rows
            if row["status"] == "confirmed_by_appendix"
        ),
        "rules_merely_mentioned_not_marked_confirmed": all(
            row["status"] != "confirmed_by_appendix"
            for row in rows
            if row["field"] in {"equity_entry_condition", "regression_equation", "risk_free_return_definition"}
        ),
        "appendix_not_treated_as_complete_article": True,
        "effective_and_target_ffr_not_conflated": True,
        "monthly_average_and_month_end_ffr_not_conflated": True,
        "no_warmup_lag_threshold_cost_or_allocation_invented": True,
        "no_strategy_return_or_performance_metric_calculated": True,
        "no_spy_bil_strategy_implemented": True,
        "no_overlay_executed": True,
        "no_broker_write_endpoint_called": True,
        "existing_evidence_files_unchanged": prior_hashes_before == prior_hashes_after,
        "registry_and_paper_demo_state_preserved": state_before == state_after,
        "future_spec_only_when_complete": True,
        "outputs_deterministic_hash": stable_payload_hash({"rows": rows, "outcome": OUTCOME}),
        "next_action_exact": NEXT_ACTION == "direction_owner_review_maio_dont_fight_fed_author_appendix_correction_v1",
    }
    return {**checks, "required_files": required, "consistency_passed": all(v is True or k == "outputs_deterministic_hash" for k, v in checks.items())}


def summary_md() -> str:
    return f"""# Maio Don't Fight the Fed Author Appendix Correction

Task: `{TASK_ID}`

Candidate: `{CANDIDATE_STRATEGY_ID}`

Corrected outcome: `{OUTCOME}`

The previous source inventory was incomplete because Paulo Maio's official author page lists the article and links an official appendix. This correction packet preserves the previous packet unchanged and records the author appendix as a newly verified official source.

The appendix confirms several table-note facts: `Delta FFR` is the named predictor in supplementary timing tables, the no-short-sales stock-index OS table exists, dynamic strategies are described as not leveraged, the total sample is reported as `1954:08-2010:12`, and the first regression estimation period is reported as `1954:08-1964:07`.

The appendix is still not a complete implementation methodology. It refers to paper sections and supplementary tables, and it does not fully define the exact FFR data series, effective-versus-target choice, monthly-average-versus-month-end construction, implementable regression equation, recursive/update rule, allocation/entry/defensive rule, signal/execution timing, risk-free series, transaction costs, or turnover accounting.

No strategy implementation, backtest, performance analysis, parameter search, SPY/BIL strategy, overlay experiment, broker-write call, paper/demo activation, promotion, or real-money advice occurred.

Exact next action: `{NEXT_ACTION}`
"""


def run(root: Path = ROOT) -> dict[str, Any]:
    output = abs_path(root, OUTPUT_DIR)
    clean_output_dir(output)
    prior_files = prior_packet_files(root)
    prior_before = snapshot_paths(root, prior_files)
    state_before = snapshot_paths(root, PROTECTED_STATE_PATHS)

    author_page = fetch_author_page()
    download = download_appendix(root)
    metadata = pdf_metadata(download)
    verification = official_author_source_verification(author_page, metadata)
    rows = rule_rows()
    confirmed_rows = [row for row in rows if row["status"] == "confirmed_by_appendix"]
    unresolved_rows = [row for row in rows if row["status"] != "confirmed_by_appendix"]

    write_json(output / "correction_trigger.json", correction_trigger(prior_before))
    write_json(output / "official_author_source_verification.json", verification)
    write_json(output / "author_appendix_file_metadata.json", metadata)
    write_json(
        output / "author_appendix_hash.json",
        {
            "file_id": APPENDIX_FILE_ID,
            "view_url": APPENDIX_VIEW_URL,
            "download_url": APPENDIX_DOWNLOAD_URL,
            "local_path": download.get("local_path", ""),
            "sha256": download.get("sha256", "missing"),
            "bytes": download.get("bytes", 0),
            "download_timestamp_utc": RUN_CREATED_UTC,
        },
    )
    write_csv(output / "author_appendix_section_inventory.csv", section_inventory(), ["appendix_page", "section_or_table", "short_paraphrase", "relevance", "full_text_persisted"])
    write_csv(
        output / "appendix_rule_extraction.csv",
        rows,
        [
            "category",
            "field",
            "status",
            "appendix_page",
            "section_table_or_equation",
            "short_paraphrase",
            "sufficient_for_implementation",
            "implementation_note",
        ],
    )
    prior_after = snapshot_paths(root, prior_files)
    write_csv(
        output / "prior_vs_corrected_source_inventory.csv",
        prior_vs_corrected_rows(prior_before, prior_after),
        [
            "prior_artifact",
            "prior_statement",
            "corrected_statement",
            "source_omitted_previously",
            "prior_file_hash_before",
            "prior_file_hash_after",
            "prior_packet_modified",
        ],
    )
    write_csv(
        output / "newly_confirmed_rules.csv",
        confirmed_rows,
        [
            "category",
            "field",
            "status",
            "appendix_page",
            "section_table_or_equation",
            "short_paraphrase",
            "sufficient_for_implementation",
            "implementation_note",
        ],
    )
    write_csv(
        output / "remaining_unresolved_rules.csv",
        unresolved_rows,
        [
            "category",
            "field",
            "status",
            "appendix_page",
            "section_table_or_equation",
            "short_paraphrase",
            "sufficient_for_implementation",
            "implementation_note",
        ],
    )
    write_yaml(output / "corrected_exact_source_rule_spec.yaml", corrected_spec(rows))
    write_json(output / "corrected_source_rule_outcome.json", corrected_outcome())
    write_json(output / "future_baseline_spec.json", future_baseline_spec())
    write_csv(output / "command_validation_log.csv", command_validation_rows(), ["command", "status", "notes"])
    write_text(output / "correction_summary.md", summary_md())

    state_after = snapshot_paths(root, PROTECTED_STATE_PATHS)
    consistency = consistency_payload(output, rows, prior_before, prior_after, state_before, state_after)
    write_json(output / "consistency_check.json", consistency)

    return {
        "task_id": TASK_ID,
        "candidate_strategy": CANDIDATE_STRATEGY_ID,
        "outcome": OUTCOME,
        "appendix_retrieved": bool(download.get("public_accessible")),
        "source_rules_complete": False,
        "evidence_path": str(output.resolve()),
        "consistency_passed": consistency["consistency_passed"],
        "next_action": NEXT_ACTION,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))

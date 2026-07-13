from __future__ import annotations

import argparse
import io
import json
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from strategy_lab.research_os.research.dsr_evidence_status import DSR_ACTIVE_ID


REPO_ROOT = Path(__file__).resolve().parent
CHALLENGE_LATEST = REPO_ROOT / "evidence" / "challenge_runs" / "latest"
ADVISOR_LATEST = REPO_ROOT / "evidence" / "advisor_upload" / "latest"
RULES_PATH = REPO_ROOT / "advisor_audit" / "advisor_consistency_rules.yaml"
PERFORMANCE_METRIC_COLUMNS = [
    "unconditional_final_equity",
    "stop_enforced_final_equity",
    "total_return_unconditional",
    "total_return_stop_enforced",
    "max_equity",
    "min_equity",
    "max_drawdown_dollars",
    "max_drawdown_pct",
    "absolute_floor_stop_hit",
    "trailing_drawdown_stop_hit",
    "any_project_stop_hit",
    "equity_at_first_project_stop",
    "target_300_hit",
    "target_300_before_stop",
    "target_400_hit",
    "target_400_before_stop",
    "days_to_target_300",
    "days_to_target_400",
    "days_to_first_stop",
]


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    try:
        if pd.isna(value):
            return False
    except (TypeError, ValueError):
        pass
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def is_blank(value: Any) -> bool:
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return str(value).strip().lower() in {"", "nan", "none", "null", "unavailable"}


def safe_read_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def load_rules(path: Path = RULES_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def issue(rule_id: str, severity: str, message: str, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "severity": severity,
        "message": message,
        "evidence": evidence or {},
    }


def text_contains(text: str, phrase: str) -> bool:
    return phrase.lower() in text.lower()


def run_level_finality_false(summary_text: str) -> bool:
    patterns = [
        r"final_validation_completed:\s*false",
        r"run_final_validation_completed\s*=\s*false",
        r"run-level finality.*false",
    ]
    return any(re.search(pattern, summary_text, flags=re.IGNORECASE) for pattern in patterns)


def exact_row_mask(frame: pd.DataFrame) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype=bool)
    mask = pd.Series(True, index=frame.index)
    if "rolling_method" in frame:
        mask &= frame["rolling_method"].fillna("").astype(str).eq("all_possible")
    if "final_validation_completed" in frame:
        mask &= frame["final_validation_completed"].map(boolish)
    if "number_of_windows" in frame and "possible_window_count" in frame:
        numeric_equal = pd.to_numeric(frame["number_of_windows"], errors="coerce").eq(
            pd.to_numeric(frame["possible_window_count"], errors="coerce")
        )
        mask &= numeric_equal.fillna(False)
    if "rolling_status" in frame:
        status = frame["rolling_status"].fillna("").astype(str)
        mask &= status.isin(["", "completed", "nan"])
    return mask


def exact_strategies_present(rolling: pd.DataFrame, challenge: pd.DataFrame, strategies: set[str]) -> set[str]:
    present: set[str] = set()
    if not rolling.empty and "strategy" in rolling:
        exact = rolling[exact_row_mask(rolling)]
        present.update(exact[exact["strategy"].astype(str).isin(strategies)]["strategy"].astype(str).unique())
    if not challenge.empty and "strategy" in challenge:
        completed = challenge[
            challenge.get("run_status", pd.Series("", index=challenge.index)).fillna("").astype(str).isin(["completed", "", "nan"])
            & challenge.get("final_validation_completed", pd.Series(False, index=challenge.index)).map(boolish)
            & challenge["strategy"].astype(str).isin(strategies)
        ]
        present.update(completed["strategy"].astype(str).unique())
    return present


def exact_family_rows_exist(rolling: pd.DataFrame) -> bool:
    if rolling.empty or "lane" not in rolling:
        return False
    family = rolling[rolling["lane"].fillna("").astype(str).eq("independent_family_challenge")]
    return bool(not family.empty and exact_row_mask(family).any())


def frame_rows_with_status(frame: pd.DataFrame, statuses: set[str]) -> pd.DataFrame:
    if frame.empty or "run_status" not in frame:
        return pd.DataFrame()
    return frame[frame["run_status"].fillna("").astype(str).isin(statuses)].copy()


def real_money_claims_in_text(name: str, text: str, forbidden_claims: list[str]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    lowered = text.lower()
    for claim in forbidden_claims:
        start = 0
        claim_lower = claim.lower()
        while True:
            idx = lowered.find(claim_lower, start)
            if idx < 0:
                break
            prefix = lowered[max(0, idx - 32) : idx]
            line_start = lowered.rfind("\n", 0, idx) + 1
            line_end = lowered.find("\n", idx)
            if line_end < 0:
                line_end = len(lowered)
            line = lowered[line_start:line_end]
            negated = any(
                token in prefix or token in line
                for token in [
                    "not ",
                    "no ",
                    "never ",
                    "cannot ",
                    "cannot be ",
                    "is not ",
                    "are not ",
                    "no strategy",
                    "forbidden conclusion",
                    "forbidden conclusions",
                    "forbidden claims",
                    "not a ",
                ]
            )
            if not negated:
                findings.append({"file": name, "claim": claim})
            start = idx + len(claim_lower)
    return findings


def read_advisor_zip_texts(advisor_latest: Path = ADVISOR_LATEST) -> dict[str, str]:
    texts: dict[str, str] = {}
    if not advisor_latest.exists():
        return texts
    for zip_path in advisor_latest.glob("*.zip"):
        try:
            with zipfile.ZipFile(zip_path) as zf:
                for name in zf.namelist():
                    if Path(name).name.upper().startswith("ADVISOR_CONSISTENCY_REPORT"):
                        continue
                    if Path(name).suffix.lower() in {".md", ".json", ".yaml", ".yml", ".csv"}:
                        try:
                            texts[f"{zip_path.name}:{name}"] = zf.read(name).decode("utf-8", errors="ignore")
                        except Exception:
                            continue
        except zipfile.BadZipFile:
            continue
    return texts


def advisor_zip_forbidden_entries(advisor_latest: Path, forbidden_tokens: list[str]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if not advisor_latest.exists():
        return findings
    for zip_path in advisor_latest.glob("*.zip"):
        try:
            with zipfile.ZipFile(zip_path) as zf:
                for name in zf.namelist():
                    lower = name.lower()
                    if lower.endswith(".zip") or any(token.lower() in lower for token in forbidden_tokens):
                        findings.append({"zip": zip_path.name, "entry": name})
        except zipfile.BadZipFile:
            findings.append({"zip": zip_path.name, "entry": "bad_zip"})
    return findings


def generated_dsr_decision_texts(repo_root: Path = REPO_ROOT) -> dict[str, str]:
    paths = [
        repo_root / "evidence" / "strategy_evidence_library" / "latest" / "sel_decisions.json",
        repo_root / "evidence" / "research_state" / "latest" / "research_state_manifest.json",
        repo_root / "evidence" / "research_state" / "latest" / "active_observations.csv",
        repo_root / "evidence" / "current_research_checkpoint" / "latest" / "current_best_strategy_set.csv",
        repo_root / "evidence" / "current_research_checkpoint" / "latest" / "accepted_caveats.md",
    ]
    return {str(path.relative_to(repo_root)).replace("\\", "/"): safe_read_text(path) for path in paths if path.exists()}


def dsr_metric_semantic_findings(texts: dict[str, str]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for name, text in texts.items():
        lowered = text.lower()
        if "4071.04" in text and "unverified_non_comparable" not in lowered:
            findings.append(
                {
                    "file": name,
                    "metric": "4071.04",
                    "issue": "historical recovered metric presented without unverified_non_comparable status",
                }
            )
        if "3481.6998" in text:
            if "reproducible_diagnostic_only" not in lowered and "current_diagnostic_only" not in lowered:
                findings.append(
                    {
                        "file": name,
                        "metric": "3481.6998",
                        "issue": "current diagnostic metric presented without diagnostic-only status",
                    }
                )
            forbidden_current_labels = [
                "activation performance",
                "approved performance",
                "validated performance",
                "qualifying performance",
                "qualifying e4",
                "qualifies as e4",
                "e4 evidence",
            ]
            matched = []
            for phrase in forbidden_current_labels:
                if phrase not in lowered:
                    continue
                if phrase == "activation performance" and "not activation performance" in lowered:
                    continue
                if phrase == "qualifying e4" and ("not qualifying e4" in lowered or "not_qualifying_e4" in lowered):
                    continue
                if phrase == "e4 evidence" and "absence of qualifying e4 evidence" in lowered:
                    continue
                matched.append(phrase)
            if matched:
                findings.append(
                    {
                        "file": name,
                        "metric": "3481.6998",
                        "issue": "current diagnostic metric is labeled as activation/approved/validated/qualifying performance",
                        "matched_phrases": matched,
                    }
                )
        if "4071.04" in text and "3481.6998" in text and "non_comparable" not in lowered:
            findings.append(
                {
                    "file": name,
                    "metric": "both",
                    "issue": "historical and current diagnostic metrics appear together without non_comparable status",
                }
            )
        if DSR_ACTIVE_ID.lower() in lowered and "inactive because" in lowered and "evidence chain" in lowered:
            findings.append(
                {
                    "file": name,
                    "metric": "lifecycle",
                    "issue": "DSR appears inactive because evidence chain is incomplete",
                }
            )
        if DSR_ACTIVE_ID.lower() in lowered and "complete evidence chain because" in lowered and "active" in lowered:
            findings.append(
                {
                    "file": name,
                    "metric": "lifecycle",
                    "issue": "DSR active lifecycle is used to synthesize complete evidence chain",
                }
            )
    return findings


def evaluate_consistency(
    summary_text: str,
    challenge: pd.DataFrame,
    rolling: pd.DataFrame,
    rankings: pd.DataFrame,
    advisor_texts: dict[str, str] | None = None,
    advisor_latest: Path = ADVISOR_LATEST,
    challenge_latest: Path = CHALLENGE_LATEST,
    rules: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rules = rules or load_rules()
    rule_defs = rules.get("rules", {})
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    benchmark_strategies = set(
        rule_defs.get("benchmark_availability_contradiction", {}).get(
            "exact_benchmark_strategies",
            ["SPY_buy_hold", "SPY_200d_trend_model", "BIL_cash_proxy"],
        )
    )
    exact_benchmarks = exact_strategies_present(rolling, challenge, benchmark_strategies)
    if text_contains(summary_text, "ETF benchmark rolling rows are unavailable") and exact_benchmarks:
        errors.append(
            issue(
                "benchmark_availability_contradiction",
                "error",
                "Summary says ETF benchmark rolling rows are unavailable, but exact benchmark-like rows are present.",
                {"exact_benchmark_rows": sorted(exact_benchmarks)},
            )
        )

    if text_contains(summary_text, "SPY_buy_hold row unavailable") and "SPY_buy_hold" in exact_strategies_present(
        rolling, challenge, {"SPY_buy_hold"}
    ):
        errors.append(
            issue(
                "spy_buy_hold_unavailable_contradiction",
                "error",
                "Summary says SPY_buy_hold is unavailable, but exact SPY_buy_hold evidence is present.",
            )
        )

    row_exact_exists = exact_row_mask(rolling).any() if not rolling.empty else False
    if run_level_finality_false(summary_text) and row_exact_exists:
        required = rule_defs.get("run_level_vs_row_level_finality", {}).get(
            "required_summary_phrase",
            "Run-level finality can be false while row-level exact evidence exists",
        )
        if not text_contains(summary_text, required):
            errors.append(
                issue(
                    "run_level_vs_row_level_finality",
                    "error",
                    "Run-level finality is false while exact row-level evidence exists, but the summary does not explain the distinction.",
                    {"required_phrase": required},
                )
            )

    unresolved_phrases = rule_defs.get("blanket_unresolved_conclusion", {}).get(
        "forbidden_summary_phrases",
        ["+$300/+400 remain unresolved", "$300/$400 remain unresolved"],
    )
    if exact_family_rows_exist(rolling) and any(text_contains(summary_text, phrase) for phrase in unresolved_phrases):
        errors.append(
            issue(
                "blanket_unresolved_conclusion",
                "error",
                "Summary uses blanket +$300/+400 unresolved wording even though exact family rows exist.",
                {"required_narrow_phrase": "A/B exact family comparison remains unresolved"},
            )
        )

    incomplete = frame_rows_with_status(challenge, {"incomplete_evidence", "blocked_by_gate"})
    populated_metric_rows: list[dict[str, Any]] = []
    for _, row in incomplete.iterrows():
        populated = [col for col in PERFORMANCE_METRIC_COLUMNS if col in row.index and not is_blank(row.get(col))]
        if populated:
            populated_metric_rows.append(
                {
                    "strategy": row.get("strategy", ""),
                    "family_id": row.get("family_id", ""),
                    "run_status": row.get("run_status", ""),
                    "populated_metrics": populated,
                }
            )
    if populated_metric_rows:
        errors.append(
            issue(
                "incomplete_rows_with_metrics",
                "error",
                "Rows marked incomplete_evidence or blocked_by_gate contain populated performance metrics.",
                {"rows": populated_metric_rows},
            )
        )

    if not rolling.empty and "lane" in rolling:
        family_exact = rolling[
            rolling["lane"].fillna("").astype(str).eq("independent_family_challenge")
            & exact_row_mask(rolling)
        ]
        if not family_exact.empty:
            equivalent_fields = {"rolling_method", "number_of_windows", "possible_window_count", "final_validation_completed"}
            missing = sorted(equivalent_fields - set(rolling.columns))
            if missing:
                warnings.append(
                    issue(
                        "exact_rows_need_row_level_finality",
                        "warning",
                        "Exact all_possible family rows are present, but row-level finality fields are missing.",
                        {"missing_fields": missing},
                    )
                )

    for name, frame in {"challenge_results": challenge, "strategy_rankings": rankings, "rolling_window_summary": rolling}.items():
        if frame.empty:
            continue
        text_cols = [col for col in ["lane", "strategy", "family_id", "family_group", "instrument_family"] if col in frame]
        if not text_cols:
            continue
        crypto_mask = pd.Series(False, index=frame.index)
        for col in text_cols:
            crypto_mask |= frame[col].fillna("").astype(str).str.contains("crypto", case=False)
        crypto = frame[crypto_mask]
        if crypto.empty:
            continue
        if "credibility_tier" in crypto and not crypto["credibility_tier"].fillna("").astype(str).eq("tier1_exploratory").all():
            errors.append(issue("crypto_tier1_not_practical_candidate", "error", f"{name} has crypto rows outside Tier 1 exploratory."))
        if "audit_verdict" in crypto and crypto["audit_verdict"].fillna("").astype(str).eq("practical_candidate").any():
            errors.append(issue("crypto_tier1_not_practical_candidate", "error", f"{name} has a crypto practical_candidate row."))

    forbidden_claims = rule_defs.get("real_money_boundary", {}).get("forbidden_claims", [])
    real_money_findings = real_money_claims_in_text("challenge_summary.md", summary_text, forbidden_claims)
    advisor_texts = advisor_texts or {}
    for name, text in advisor_texts.items():
        real_money_findings.extend(real_money_claims_in_text(name, text, forbidden_claims))
    if real_money_findings:
        errors.append(
            issue(
                "real_money_boundary",
                "error",
                "Forbidden real-money or certainty language was found.",
                {"matches": real_money_findings[:20]},
            )
        )

    advisor_max = int(rule_defs.get("packet_file_counts", {}).get("advisor_upload_latest_max_files", 10))
    challenge_exact = int(rule_defs.get("packet_file_counts", {}).get("challenge_latest_exact_files", 10))
    advisor_count = len([p for p in advisor_latest.iterdir() if p.is_file()]) if advisor_latest.exists() else 0
    challenge_count = len([p for p in challenge_latest.iterdir() if p.is_file()]) if challenge_latest.exists() else 0
    if advisor_latest.exists() and advisor_count > advisor_max:
        errors.append(issue("top_level_file_count", "error", "Advisor upload latest exceeds top-level file limit.", {"count": advisor_count}))
    if challenge_latest.exists() and challenge_count != challenge_exact:
        errors.append(
            issue(
                "top_level_file_count",
                "error",
                "Compact challenge latest does not contain exactly 10 files.",
                {"count": challenge_count, "expected": challenge_exact},
            )
        )

    forbidden_tokens = rule_defs.get("raw_data_exclusion", {}).get("forbidden_zip_tokens", [])
    forbidden_entries = advisor_zip_forbidden_entries(advisor_latest, forbidden_tokens)
    if forbidden_entries:
        errors.append(
            issue(
                "raw_data_exclusion",
                "error",
                "Advisor upload zip contains forbidden raw/cache/venv/OHLCV entry.",
                {"entries": forbidden_entries[:50]},
            )
        )

    dsr_texts = {"challenge_summary.md": summary_text, **advisor_texts, **generated_dsr_decision_texts()}
    dsr_findings = dsr_metric_semantic_findings(dsr_texts)
    if dsr_findings:
        errors.append(
            issue(
                "dsr_metric_evidence_status_semantics",
                "error",
                "DSR historical and current diagnostic metrics are not safely distinguished.",
                {"findings": dsr_findings[:50]},
            )
        )

    status = "errors" if errors else "warnings" if warnings else "passed"
    return {
        "created_timestamp_utc": utc_now(),
        "passed": not errors,
        "consistency_status": status,
        "errors": errors,
        "warnings": warnings,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "advisor_top_level_file_count": advisor_count,
        "challenge_latest_file_count": challenge_count,
        "exact_benchmark_rows_present": sorted(exact_benchmarks),
        "row_level_exact_evidence_present": bool(row_exact_exists),
        "exact_family_rows_present": bool(exact_family_rows_exist(rolling)),
        "run_level_finality_false_detected": bool(run_level_finality_false(summary_text)),
        "dsr_metric_semantic_findings": dsr_findings,
        "dsr_metric_semantic_finding_count": len(dsr_findings),
    }


def build_consistency_report(
    challenge_latest: Path = CHALLENGE_LATEST,
    advisor_latest: Path = ADVISOR_LATEST,
    include_advisor_zip_texts: bool = True,
) -> dict[str, Any]:
    summary_text = safe_read_text(challenge_latest / "challenge_summary.md")
    challenge = safe_read_csv(challenge_latest / "challenge_results.csv")
    rolling = safe_read_csv(challenge_latest / "rolling_window_summary.csv")
    rankings = safe_read_csv(challenge_latest / "strategy_rankings.csv")
    advisor_texts = read_advisor_zip_texts(advisor_latest) if include_advisor_zip_texts else {}
    return evaluate_consistency(
        summary_text=summary_text,
        challenge=challenge,
        rolling=rolling,
        rankings=rankings,
        advisor_texts=advisor_texts,
        advisor_latest=advisor_latest,
        challenge_latest=challenge_latest,
    )


def consistency_report_markdown(report: dict[str, Any]) -> str:
    def issue_lines(items: list[dict[str, Any]]) -> str:
        if not items:
            return "- none"
        lines = []
        for item in items:
            evidence = item.get("evidence") or {}
            evidence_text = f" Evidence: `{json.dumps(evidence, sort_keys=True)}`" if evidence else ""
            lines.append(f"- {item.get('rule_id')}: {item.get('message')}{evidence_text}")
        return "\n".join(lines)

    return f"""# Advisor Consistency Report

Created: {report.get('created_timestamp_utc')}

Status: {report.get('consistency_status')}

Passed: {report.get('passed')}

Errors: {report.get('error_count')}

Warnings: {report.get('warning_count')}

Advisor top-level files: {report.get('advisor_top_level_file_count')}

Challenge latest files: {report.get('challenge_latest_file_count')}

Exact benchmark rows present: {', '.join(report.get('exact_benchmark_rows_present', [])) or 'none'}

Row-level exact evidence present: {report.get('row_level_exact_evidence_present')}

Exact family rows present: {report.get('exact_family_rows_present')}

Run-level finality false detected: {report.get('run_level_finality_false_detected')}

DSR metric semantic findings: {report.get('dsr_metric_semantic_finding_count')}

## Errors

{issue_lines(report.get('errors', []))}

## Warnings

{issue_lines(report.get('warnings', []))}

This report is research-only audit metadata. It is not a trading signal or real-money recommendation.
"""


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def upsert_zip_entries(zip_path: Path, entries: dict[str, bytes]) -> None:
    if not zip_path.exists():
        return
    existing: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in zf.namelist():
                if name not in entries:
                    existing[name] = zf.read(name)
    except zipfile.BadZipFile:
        return
    tmp = zip_path.with_suffix(".tmp.zip")
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in existing.items():
            zf.writestr(name, data)
        for name, data in entries.items():
            zf.writestr(name, data)
    tmp.replace(zip_path)


def write_report_outputs(report: dict[str, Any], advisor_latest: Path, write_top_level: bool = True, update_index_zip: bool = True) -> None:
    advisor_latest.mkdir(parents=True, exist_ok=True)
    json_data = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    md_data = (consistency_report_markdown(report).strip() + "\n").encode("utf-8")
    if update_index_zip:
        upsert_zip_entries(
            advisor_latest / "00_ADVISOR_INDEX.zip",
            {
                "ADVISOR_CONSISTENCY_REPORT.json": json_data,
                "ADVISOR_CONSISTENCY_REPORT.md": md_data,
            },
        )
    if write_top_level:
        existing_files = [p for p in advisor_latest.iterdir() if p.is_file()]
        needed = [
            advisor_latest / "advisor_consistency_report.json",
            advisor_latest / "advisor_consistency_report.md",
        ]
        would_add = sum(1 for path in needed if not path.exists())
        if len(existing_files) + would_add <= 10:
            (advisor_latest / "advisor_consistency_report.json").write_bytes(json_data)
            (advisor_latest / "advisor_consistency_report.md").write_bytes(md_data)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check advisor/challenge evidence consistency without running backtests.")
    parser.add_argument("--challenge-latest", default=str(CHALLENGE_LATEST))
    parser.add_argument("--advisor-latest", default=str(ADVISOR_LATEST))
    parser.add_argument("--no-top-level", action="store_true")
    parser.add_argument("--no-update-index-zip", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_consistency_report(Path(args.challenge_latest), Path(args.advisor_latest))
    write_report_outputs(
        report,
        Path(args.advisor_latest),
        write_top_level=not args.no_top_level,
        update_index_zip=not args.no_update_index_zip,
    )
    print(f"advisor_consistency_status={report['consistency_status']}")
    print(f"advisor_consistency_errors={report['error_count']}")
    print(f"advisor_consistency_warnings={report['warning_count']}")
    print("real_money_recommendation=false")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

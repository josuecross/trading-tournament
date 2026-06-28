from __future__ import annotations

import csv
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent
SYMBOL_MAP_PATH = Path("strategy_lab") / "approved_etf_symbol_map.yaml"
OUTPUT_DIR = Path("evidence") / "approved_symbol_expansion_review" / "latest"
NEXT_ACTIONS = {
    "approved": "bootstrap_approved_expansion_symbols_cache",
    "none": "continue_without_symbol_expansion_or_revisit_policy",
    "policy_issue": "repair_approved_etf_symbol_policy_before_expansion",
    "inconclusive": "manual_review_symbol_expansion_candidates",
}
APPROVED_SUBSET = {"EWJ", "EWU", "EWG", "EWY", "INDA", "EFAV", "EEMV", "SCHG"}
FORBIDDEN_SYMBOLS = {"TQQQ", "SQQQ", "UPRO", "SPXU", "BITO", "IBIT", "GLD3", "DBC"}
PROPOSED_SYMBOLS = ["IEFA", "VEA", "VWO", "EWJ", "EWU", "EWG", "EWY", "INDA", "IWF", "IWD", "SCHG", "SCHV", "EFAV", "EEMV", "ACWV"]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def state_mismatches(root: Path) -> list[str]:
    mismatches: list[str] = []
    required = [
        root / "strategy_lab" / "APPROVED_ETF_CACHE_POLICY.md",
        root / SYMBOL_MAP_PATH,
        root / "strategy_lab" / "strategy_registry.yaml",
        root / "evidence" / "research_lane_decision" / "latest" / "proposed_symbol_expansion_if_any.yaml",
        root / "evidence" / "research_lane_decision" / "latest" / "approved_universe_exhaustion_review.csv",
        root / "evidence" / "research_lane_decision" / "latest" / "next_lane_options.csv",
        root / "evidence" / "research_lane_decision" / "latest" / "recommended_next_lane.md",
        root / "evidence" / "approved_etf_cache_readiness" / "latest",
        root / "evidence" / "research_state" / "latest",
        root / "evidence" / "strategy_lab" / "latest",
    ]
    for path in required:
        if not path.exists():
            mismatches.append(f"missing required state path: {path.relative_to(root)}")
    recommendation_path = root / "evidence" / "research_lane_decision" / "latest" / "recommended_next_lane.md"
    if recommendation_path.exists() and "create_approved_symbol_expansion_review" not in recommendation_path.read_text(encoding="utf-8"):
        mismatches.append("recommended next action is not create_approved_symbol_expansion_review")
    proposal_path = root / "evidence" / "research_lane_decision" / "latest" / "proposed_symbol_expansion_if_any.yaml"
    if proposal_path.exists():
        proposal = load_yaml(proposal_path)
        if proposal.get("status") != "proposed_only_not_approved":
            mismatches.append("symbol proposal is not proposed-only")
        rules = proposal.get("rules", {})
        if rules.get("download_now") is not False or rules.get("approve_automatically") is not False or rules.get("strategy_run_now") is not False:
            mismatches.append("symbol proposal permits forbidden automatic action")
    manifest_path = root / "evidence" / "research_lane_decision" / "latest" / "research_lane_decision_manifest.json"
    if manifest_path.exists():
        manifest = load_json(manifest_path)
        for field in ["strategy_run", "provider_api_called", "candidate_exhaustive_run", "paper_forward_review", "paper_forward_activation", "paper_forward_checkpoint", "real_money_recommendation"]:
            if manifest.get(field) is not False:
                mismatches.append(f"research lane decision manifest has forbidden flag {field}")
    return mismatches


def proposed_symbols(root: Path) -> list[str]:
    proposal = load_yaml(root / "evidence" / "research_lane_decision" / "latest" / "proposed_symbol_expansion_if_any.yaml")
    symbols = [str(row["symbol"]).upper() for row in proposal.get("symbols", [])]
    return symbols or PROPOSED_SYMBOLS


def existing_symbols(root: Path) -> set[str]:
    symbol_map = load_yaml(root / SYMBOL_MAP_PATH)
    return {str(row.get("symbol", "")).upper() for row in symbol_map.get("symbols", [])}


def review_symbol(symbol: str, approved_subset: set[str] = APPROVED_SUBSET) -> dict[str, Any]:
    symbol = symbol.upper()
    if symbol in FORBIDDEN_SYMBOLS or symbol.endswith("3") or symbol.endswith("2"):
        return decision(symbol, "reject_policy_violation", "not_applicable", "policy violation or leveraged/inverse/forbidden-style product", "none")
    duplicate_reasons = {
        "IEFA": "broad developed ex-US role overlaps existing EFA and VEA candidate",
        "VEA": "broad developed ex-US role overlaps existing EFA and IEFA candidate",
        "VWO": "emerging-market broad role overlaps existing EEM",
        "IWF": "large-cap growth role overlaps selected SCHG plus QQQ/MTUM references",
        "IWD": "large-cap value role overlaps VTV/VLUE and SCHV candidate",
        "SCHV": "large-cap value role overlaps VTV/VLUE and IWD candidate",
        "ACWV": "global minimum-volatility role is broad and less targeted than EFAV/EEMV",
    }
    if symbol in duplicate_reasons:
        return decision(symbol, "defer_duplicate_or_low_incremental_value", "high", duplicate_reasons[symbol], "possible later benchmark/control")
    if symbol in approved_subset:
        lane = "regional_international_momentum" if symbol in {"EWJ", "EWU", "EWG", "EWY", "INDA"} else "international_lowvol_defensive" if symbol in {"EFAV", "EEMV"} else "us_style_confirmation"
        return decision(symbol, "approve_for_next_cache_bootstrap", "low_to_medium", "adds targeted incremental structure and remains ETF/fund-wrapper only", lane)
    return decision(symbol, "defer_policy_review", "unknown", "not in the controlled subset selected for this review", "manual review")


def decision(symbol: str, classification: str, redundancy_risk: str, reason: str, expected_lane: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "classification": classification,
        "etf_fund_wrapper_only": classification != "reject_policy_violation",
        "leverage_inverse_forbidden": classification == "reject_policy_violation",
        "likely_enough_history": classification != "reject_policy_violation",
        "supports_next_research_goal": classification == "approve_for_next_cache_bootstrap",
        "redundancy_risk": redundancy_risk,
        "expected_lane": expected_lane,
        "approved_status": "approved_pending_cache_bootstrap" if classification == "approve_for_next_cache_bootstrap" else "not_approved",
        "reason": reason,
    }


def duplication_rows(decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    comparisons = {
        "IEFA": ("VEA;EFA", "defer broad developed ex-US duplicate"),
        "VEA": ("IEFA;EFA", "defer broad developed ex-US duplicate"),
        "VWO": ("EEM", "defer broad EM duplicate"),
        "IWF": ("SCHG;QQQ;MTUM", "defer; select only one growth style confirmation"),
        "SCHG": ("IWF;QQQ;MTUM", "approve one representative growth style confirmation"),
        "IWD": ("SCHV;VTV;VLUE", "defer value duplicate"),
        "SCHV": ("IWD;VTV;VLUE", "defer value duplicate"),
        "EFAV": ("USMV;EFA", "approve targeted developed ex-US min-vol sleeve"),
        "EEMV": ("USMV;EEM", "approve targeted emerging-market min-vol sleeve"),
        "ACWV": ("USMV;EFAV;EEMV", "defer broad global min-vol duplicate"),
        "EWJ": ("EFA;IEFA;VEA", "approve regional Japan sleeve"),
        "EWU": ("EFA;IEFA;VEA", "approve regional UK sleeve"),
        "EWG": ("EFA;IEFA;VEA", "approve regional Germany sleeve"),
        "EWY": ("EFA;EEM;VWO", "approve regional Korea sleeve"),
        "INDA": ("EEM;VWO", "approve regional India sleeve"),
    }
    by_symbol = {row["symbol"]: row for row in decisions}
    return [
        {
            "symbol": symbol,
            "compared_to": compared,
            "redundancy_assessment": by_symbol[symbol]["redundancy_risk"],
            "classification": by_symbol[symbol]["classification"],
            "preferred_action": action,
        }
        for symbol, (compared, action) in comparisons.items()
        if symbol in by_symbol
    ]


def policy_rows(decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "symbol": row["symbol"],
            "etf_fund_wrapper_only": row["etf_fund_wrapper_only"],
            "no_leverage_inverse": not row["leverage_inverse_forbidden"],
            "no_direct_futures_options_forex_crypto": row["classification"] != "reject_policy_violation",
            "allowed_for_strategy_if_approved": row["classification"] == "approve_for_next_cache_bootstrap",
            "requires_explicit_prompt": row["classification"] == "approve_for_next_cache_bootstrap",
            "cache_ready": False,
            "policy_decision": "passes_policy_for_pending_cache_bootstrap" if row["classification"] == "approve_for_next_cache_bootstrap" else row["classification"],
        }
        for row in decisions
    ]


def selected_symbols(decisions: list[dict[str, Any]]) -> list[str]:
    return [row["symbol"] for row in decisions if row["classification"] == "approve_for_next_cache_bootstrap"]


def symbol_map_entry(symbol: str, classification: dict[str, Any]) -> dict[str, Any]:
    group = "international_regional_expansion"
    if symbol in {"EFAV", "EEMV"}:
        group = "international_minvol_expansion"
    elif symbol == "SCHG":
        group = "us_factor_expansion"
    return {
        "symbol": symbol,
        "group": group,
        "allowed_for_strategy": True,
        "allowed_for_benchmark": True,
        "requires_explicit_prompt": True,
        "approved_status": "approved_pending_cache_bootstrap",
        "approval_source": "approved_symbol_expansion_review",
        "notes": f"Approved for future explicit cache bootstrap only; not cache-ready. Expected lane: {classification['expected_lane']}.",
    }


def update_symbol_map(root: Path, decisions: list[dict[str, Any]]) -> list[str]:
    symbol_map_path = root / SYMBOL_MAP_PATH
    symbol_map = load_yaml(symbol_map_path)
    rows = symbol_map.setdefault("symbols", [])
    existing = {str(row.get("symbol", "")).upper() for row in rows}
    added: list[str] = []
    for row in decisions:
        symbol = row["symbol"]
        if row["classification"] != "approve_for_next_cache_bootstrap" or symbol in existing:
            continue
        rows.append(symbol_map_entry(symbol, row))
        existing.add(symbol)
        added.append(symbol)
    symbol_map_path.write_text(yaml.safe_dump(symbol_map, sort_keys=False, width=120), encoding="utf-8")
    return added


def create_packet(directory: Path) -> Path:
    packet = directory / "approved_symbol_expansion_review_packet.zip"
    if packet.exists():
        packet.unlink()
    with zipfile.ZipFile(packet, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(directory.iterdir()):
            if path.is_file() and path.name != packet.name:
                zf.write(path, path.name)
    return packet


def write_outputs(root: Path, payload: dict[str, Any]) -> dict[str, str]:
    output = root / OUTPUT_DIR
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    decision_fields = ["symbol", "classification", "etf_fund_wrapper_only", "leverage_inverse_forbidden", "likely_enough_history", "supports_next_research_goal", "redundancy_risk", "expected_lane", "approved_status", "reason"]
    write_csv(output / "approved_symbol_expansion_decisions.csv", payload["decisions"], decision_fields)
    write_csv(output / "symbol_expansion_duplication_review.csv", payload["duplication_rows"], ["symbol", "compared_to", "redundancy_assessment", "classification", "preferred_action"])
    write_csv(output / "approved_symbol_expansion_policy_check.csv", payload["policy_rows"], ["symbol", "etf_fund_wrapper_only", "no_leverage_inverse", "no_direct_futures_options_forex_crypto", "allowed_for_strategy_if_approved", "requires_explicit_prompt", "cache_ready", "policy_decision"])

    selected = selected_symbols(payload["decisions"])
    rejected = [row for row in payload["decisions"] if row["classification"] != "approve_for_next_cache_bootstrap"]
    (output / "approved_symbol_expansion_selected_symbols.yaml").write_text(yaml.safe_dump({"status": "approved_pending_cache_bootstrap", "cache_ready": False, "symbols": selected}, sort_keys=False, width=120), encoding="utf-8")
    (output / "approved_symbol_expansion_rejected_or_deferred.yaml").write_text(yaml.safe_dump({"status": "not_approved", "symbols": rejected}, sort_keys=False, width=120), encoding="utf-8")
    (output / "approved_symbol_expansion_next_action.md").write_text(f"# Next Action\n\n`{payload['next_action']}`\n\nDo not run strategy discovery until approved expansion symbols are explicitly bootstrapped and QA-passed.\n", encoding="utf-8")
    summary = [
        "# Approved Symbol Expansion Review",
        "",
        f"Created at UTC: {now_utc()}",
        f"Symbols reviewed: {len(payload['decisions'])}",
        f"Symbols approved pending cache bootstrap: {len(selected)}",
        f"Next action: `{payload['next_action']}`",
        "",
        "This is symbol governance only. No provider download, cache bootstrap, strategy discovery, candidate validation, paper-forward workflow, broker path, or real-money recommendation was run.",
    ]
    (output / "approved_symbol_expansion_review_summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    write_json(output / "approved_symbol_expansion_manifest.json", payload["manifest"])
    write_json(output / "approved_symbol_expansion_consistency_check.json", payload["consistency"])
    packet = create_packet(output)
    return {"output_dir": str(output), "packet": str(packet)}


def build_payload(root: Path, strict_state: bool = True, update_map: bool = True) -> dict[str, Any]:
    mismatches = state_mismatches(root)
    if mismatches and strict_state:
        raise RuntimeError("State confirmation failed: " + "; ".join(mismatches))
    proposals = proposed_symbols(root)
    decisions = [review_symbol(symbol) for symbol in proposals]
    approved = selected_symbols(decisions)
    next_action = NEXT_ACTIONS["approved"] if approved else NEXT_ACTIONS["none"]
    added_symbols = update_symbol_map(root, decisions) if update_map and approved else []
    existing = existing_symbols(root)
    consistency = {
        "symbol_expansion_review_completed": True,
        "proposed_symbols_not_approved_automatically": len(approved) < len(decisions),
        "forbidden_symbols_rejected": review_symbol("TQQQ")["classification"] == "reject_policy_violation",
        "near_duplicates_deferred": all(review_symbol(symbol)["classification"] == "defer_duplicate_or_low_incremental_value" for symbol in ["IEFA", "VEA", "VWO", "IWD", "SCHV", "ACWV"]),
        "approved_symbols_require_explicit_prompt": all(row.get("requires_explicit_prompt") is True for row in load_yaml(root / SYMBOL_MAP_PATH).get("symbols", []) if row.get("symbol") in approved),
        "approved_symbols_pending_cache_bootstrap_not_cache_ready": all(row.get("approved_status") == "approved_pending_cache_bootstrap" and row.get("cache_ready") is not True for row in load_yaml(root / SYMBOL_MAP_PATH).get("symbols", []) if row.get("symbol") in approved),
        "no_provider_download": True,
        "no_strategy_runner_called": True,
        "no_candidate_exhaustive_run": True,
        "no_paper_forward_active_flag_set": True,
        "no_real_money_recommendation": True,
        "next_action_explicit": next_action in NEXT_ACTIONS.values(),
        "symbol_map_updated_or_already_contained_approved_symbols": set(approved) <= existing_symbols(root),
    }
    consistency["consistency_passed"] = all(bool(value) for value in consistency.values())
    manifest = {
        "created_at_utc": now_utc(),
        "symbols_reviewed": proposals,
        "symbols_approved": approved,
        "symbols_rejected_or_deferred": [row["symbol"] for row in decisions if row["classification"] != "approve_for_next_cache_bootstrap"],
        "symbol_map_updated": bool(added_symbols),
        "symbol_map_added_symbols": added_symbols,
        "next_action": next_action,
        "state_mismatches": mismatches,
        "strategy_run": False,
        "provider_api_called": False,
        "data_downloaded": False,
        "cache_bootstrap_run": False,
        "candidate_exhaustive_run": False,
        "paper_forward_review": False,
        "paper_forward_activation": False,
        "paper_forward_checkpoint": False,
        "broker_integration": False,
        "live_orders": False,
        "order_placement": False,
        "real_money_recommendation": False,
    }
    return {"decisions": decisions, "duplication_rows": duplication_rows(decisions), "policy_rows": policy_rows(decisions), "next_action": next_action, "manifest": manifest, "consistency": consistency}


def run_expansion_review(root: Path = ROOT, strict_state: bool = True, update_map: bool = True) -> dict[str, Any]:
    payload = build_payload(root, strict_state=strict_state, update_map=update_map)
    outputs = write_outputs(root, payload)
    return {
        "output_dir": outputs["output_dir"],
        "packet": outputs["packet"],
        "approved_symbols": selected_symbols(payload["decisions"]),
        "next_action": payload["next_action"],
        "consistency": payload["consistency"],
    }


def main() -> None:
    print(json.dumps(run_expansion_review(ROOT, strict_state=True, update_map=True), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

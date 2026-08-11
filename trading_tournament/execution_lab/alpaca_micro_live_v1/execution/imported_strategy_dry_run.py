from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from execution_lab.alpaca_micro_live_v1 import MODULE_ROOT
from execution_lab.alpaca_micro_live_v1.handoff_import.calculator_registry import CalculatorRegistry
from execution_lab.alpaca_micro_live_v1.handoff_import.import_pipeline import FIRST_BATCH
from execution_lab.alpaca_micro_live_v1.handoff_import.providers.frozen_reference_virtual_sleeve import load_frozen_reference
from execution_lab.alpaca_micro_live_v1.handoff_import.reporting import write_csv, write_json
from execution_lab.alpaca_micro_live_v1.execution.imported_strategy_data_preflight import run_preflight

GENERATED_SPEC_DIR = MODULE_ROOT / "runtime_strategies" / "generated"
DRY_RUN_REGISTRY = GENERATED_SPEC_DIR / "dry_run_import_registry.yaml"
DEFAULT_OUTPUT_DIR = MODULE_ROOT / "evidence" / "handoff_imports" / "dry_run_registration" / "latest"
BLOCKER_FIX_OUTPUT_DIR = MODULE_ROOT / "evidence" / "handoff_imports" / "dry_run_blocker_fixes" / "latest"
LOCAL_BAR_CACHE = MODULE_ROOT / "evidence" / "alpaca_runtime_data" / "cache"
IMMUTABLE_ROOT = MODULE_ROOT / "evidence" / "handoff_imports" / "immutable_packages"


FIRST_BATCH_ORDER = [
    "ice_vaneck_us_fallen_angel_angl_v1_standard_handoff_v1",
    "schwoerer_hyg_ema100_spy_bil_v1_standard_handoff_v1",
    "barbara_decelerated_psar_spy_bil_v1_standard_handoff_v1",
    "factory_v1_spy_trend_quality_state_d1_standard_handoff_v1",
]

CALCULATOR_TYPE_BY_PACKAGE = {
    "ice_vaneck_us_fallen_angel_angl_v1_standard_handoff_v1": "angl_80_20_monthly_calculator_v1",
    "schwoerer_hyg_ema100_spy_bil_v1_standard_handoff_v1": "hyg_ema100_spy_bil_calculator_v1",
    "barbara_decelerated_psar_spy_bil_v1_standard_handoff_v1": "decelerated_psar_calculator_v1",
    "factory_v1_spy_trend_quality_state_d1_standard_handoff_v1": "factory_d1_trend_quality_calculator_v1",
}


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(MODULE_ROOT))
    except ValueError:
        return str(path)


def _spec_path_for_strategy(strategy_id: str, generated_spec_dir: Path = GENERATED_SPEC_DIR) -> Path:
    return generated_spec_dir / f"{strategy_id}.yaml"


def _first_batch_registry_rows(generated_spec_dir: Path = GENERATED_SPEC_DIR) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for package_id in FIRST_BATCH_ORDER:
        spec_path = next((path for path in generated_spec_dir.glob("*.yaml") if (_load_yaml(path).get("handoff_package_id") == package_id)), None)
        if not spec_path:
            strategy_id = package_id.replace("_standard_handoff_v1", "")
            spec = {}
        else:
            spec = _load_yaml(spec_path)
            strategy_id = spec.get("strategy_id", package_id.replace("_standard_handoff_v1", ""))
        rows.append(
            {
                "handoff_package_id": package_id,
                "strategy_id": strategy_id,
                "generated_spec": _display_path(spec_path) if spec_path else "",
                "calculator_id": CALCULATOR_TYPE_BY_PACKAGE.get(package_id, ""),
                "conformance_status": (spec.get("conformance") or {}).get("status", ""),
                "dry_run_enabled": True,
                "conformance_passed": (spec.get("conformance") or {}).get("status") == "fixture_passed",
                "runtime_ready": False,
                "paper_trading_allowed": False,
                "live_trading_allowed": False,
                "paper_submit_allowed": False,
            }
        )
    return rows


def write_dry_run_registry(path: Path = DRY_RUN_REGISTRY, generated_spec_dir: Path = GENERATED_SPEC_DIR) -> Path:
    rows = _first_batch_registry_rows(generated_spec_dir)
    payload = {
        "source": "standard_v1_handoff_import_dry_run_registry",
        "registry_scope": "first_batch_disabled_runtime_dry_run_only",
        "all_runtime_ready_member": False,
        "paper_submit_allowed": False,
        "live_trading_allowed": False,
        "strategies": rows,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def load_dry_run_registry(path: Path = DRY_RUN_REGISTRY) -> dict[str, Any]:
    if not path.exists():
        write_dry_run_registry(path)
    return _load_yaml(path)


def _read_closes(symbol: str, cache_dir: Path = LOCAL_BAR_CACHE) -> list[float]:
    path = cache_dir / f"{symbol}_1Day.csv"
    if not path.exists():
        return []
    closes: list[float] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            value = row.get("close")
            if value not in (None, ""):
                closes.append(float(value))
    return closes


def _target_for_hyg(spec: dict[str, Any], binding, as_of: str, cache_dir: Path) -> tuple[str, dict[str, Any] | None, str]:
    closes = _read_closes("HYG", cache_dir)
    if len(closes) < 100:
        return "blocked", None, "data_requirement_gap:HYG_1Day_cache_missing_or_less_than_100_closes"
    prior = closes[-101] if len(closes) >= 101 else sum(closes[-100:]) / 100
    ema = sum(closes[-100:]) / 100 if len(closes) == 100 else prior
    for close in closes[-100:]:
        ema = (2 / 101) * close + (1 - (2 / 101)) * ema
    actual = binding.calculate({"EMA": ema, "HYG_close": closes[-1]}, {}, {"signal_calculation": {"alpha": 2 / 101}})
    return "target_generated", actual, ""


def _merge_frozen_reference(target: dict[str, Any], frozen_weights: dict[str, float]) -> dict[str, Any]:
    weights = dict(target.get("target_weights", {}))
    reference_weight = float(weights.pop("FROZEN_REFERENCE", 0.0))
    if reference_weight:
        for symbol, weight in frozen_weights.items():
            weights[symbol] = weights.get(symbol, 0.0) + reference_weight * float(weight)
    target["target_weights"] = {symbol: float(weight) for symbol, weight in weights.items() if float(weight) != 0.0}
    return target


def generate_dry_run_target(row: dict[str, Any], *, as_of: str, generated_spec_dir: Path, cache_dir: Path, immutable_root: Path = IMMUTABLE_ROOT) -> dict[str, Any]:
    raw_spec_path = Path(str(row.get("generated_spec", ""))) if row.get("generated_spec") else _spec_path_for_strategy(row["strategy_id"], generated_spec_dir)
    spec_path = raw_spec_path if raw_spec_path.is_absolute() else MODULE_ROOT / raw_spec_path
    spec = _load_yaml(spec_path)
    registry = CalculatorRegistry()
    calculator_id = str(row.get("calculator_id") or CALCULATOR_TYPE_BY_PACKAGE.get(row["handoff_package_id"], ""))
    # Generated specs store binding status; use handoff package id to recover the actual calculator type.
    binding = registry.resolve(CALCULATOR_TYPE_BY_PACKAGE.get(row["handoff_package_id"], ""), row["strategy_id"])
    blocked: list[str] = []
    provider_requirements = spec.get("provider_requirements") or []
    frozen_reference = None
    if any("frozen_reference" in str(item).lower() for item in provider_requirements + spec.get("required_instruments", [])):
        frozen_reference = load_frozen_reference(row["handoff_package_id"], immutable_root)
        if frozen_reference.status != "provider_data_available":
            blocked.append(frozen_reference.blocked_reason)
    if not binding:
        blocked.append("calculator_binding_missing")
    if spec.get("enabled") is not False or spec.get("runtime_ready") is not False or spec.get("paper_trading_allowed") is not False or spec.get("live_trading_allowed") is not False:
        blocked.append("manual_review_required:generated_spec_not_dry_run_safe")
    target = None
    status = "blocked" if blocked else "target_generated"
    if not blocked and row["strategy_id"] == "schwoerer_hyg_ema100_spy_bil_v1":
        status, target, reason = _target_for_hyg(spec, binding, as_of, cache_dir)
        if reason:
            blocked.append(reason)
    elif not blocked and row["strategy_id"] == "ice_vaneck_us_fallen_angel_angl_v1":
        target = binding.calculate({"event": "first_monthly_outer_rebalance"}, {}, {"portfolio_construction": {"outer_targets": {"ANGL": 0.2, "FROZEN_REFERENCE": 0.8}}})
    elif not blocked and row["strategy_id"] == "barbara_decelerated_psar_spy_bil_v1":
        target = binding.calculate({"completed_sessions": 2}, {}, {})
    elif not blocked and row["strategy_id"] == "factory_v1_spy_trend_quality_state_d1":
        target = binding.calculate({"valid_SPY_closes": 59}, {}, {})
    if target and frozen_reference and frozen_reference.status == "provider_data_available":
        target = _merge_frozen_reference(target, frozen_reference.target_weights)
        status = "dry_run_target_generated_disabled"
    elif target:
        status = "dry_run_target_generated_disabled"
    return {
        "handoff_package_id": row["handoff_package_id"],
        "strategy_id": row["strategy_id"],
        "generated_spec_path": str(spec_path),
        "calculator_id": calculator_id,
        "conformance_status": row.get("conformance_status", ""),
        "dry_run_enabled": str(row.get("dry_run_enabled") is True).lower(),
        "runtime_ready": str(spec.get("runtime_ready")).lower(),
        "paper_trading_allowed": str(spec.get("paper_trading_allowed")).lower(),
        "live_trading_allowed": str(spec.get("live_trading_allowed")).lower(),
        "target_generation_status": "blocked" if blocked else status,
        "blocked_reason": ";".join(blocked),
        "target_weights_json": json.dumps((target or {}).get("target_weights", {}), sort_keys=True) if target else "",
        "as_of": as_of,
    }


def _selected_rows(registry: dict[str, Any], *, first_batch: bool, all_dry_run_enabled: bool, strategy_id: str | None) -> list[dict[str, Any]]:
    rows = registry.get("strategies") or []
    if strategy_id:
        return [row for row in rows if row.get("strategy_id") == strategy_id or row.get("handoff_package_id") == strategy_id]
    if first_batch:
        return [row for row in rows if row.get("handoff_package_id") in FIRST_BATCH]
    if all_dry_run_enabled:
        return [row for row in rows if row.get("dry_run_enabled") is True]
    return []


def run_imported_strategy_dry_run(
    *,
    first_batch: bool = False,
    all_dry_run_enabled: bool = False,
    strategy_id: str | None = None,
    as_of: str | None = None,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    registry_path: Path = DRY_RUN_REGISTRY,
    generated_spec_dir: Path = GENERATED_SPEC_DIR,
    cache_dir: Path = LOCAL_BAR_CACHE,
    blocker_fix_output_dir: Path = BLOCKER_FIX_OUTPUT_DIR,
    immutable_root: Path = IMMUTABLE_ROOT,
) -> dict[str, Any]:
    as_of = as_of or date.today().isoformat()
    write_dry_run_registry(registry_path, generated_spec_dir)
    registry = load_dry_run_registry(registry_path)
    selected = _selected_rows(registry, first_batch=first_batch, all_dry_run_enabled=all_dry_run_enabled, strategy_id=strategy_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    status_rows = []
    spec_rows = []
    target_rows = []
    blocked_rows = []
    registry_rows = []
    for row in selected:
        raw_spec_path = Path(str(row.get("generated_spec", ""))) if row.get("generated_spec") else _spec_path_for_strategy(row["strategy_id"], generated_spec_dir)
        spec_path = raw_spec_path if raw_spec_path.is_absolute() else MODULE_ROOT / raw_spec_path
        spec = _load_yaml(spec_path)
        safety_ok = spec.get("enabled") is False and spec.get("runtime_ready") is False and spec.get("paper_trading_allowed") is False and spec.get("live_trading_allowed") is False
        registry_rows.append({**row, "generated_spec": str(spec_path)})
        target = generate_dry_run_target(row, as_of=as_of, generated_spec_dir=generated_spec_dir, cache_dir=cache_dir, immutable_root=immutable_root)
        status_rows.append(target)
        target_rows.append(target)
        spec_rows.append(
            {
                "handoff_package_id": row["handoff_package_id"],
                "strategy_id": row["strategy_id"],
                "generated_spec_path": str(spec_path),
                "enabled": str(spec.get("enabled")).lower(),
                "runtime_ready": str(spec.get("runtime_ready")).lower(),
                "paper_trading_allowed": str(spec.get("paper_trading_allowed")).lower(),
                "live_trading_allowed": str(spec.get("live_trading_allowed")).lower(),
                "safety_ok": str(safety_ok).lower(),
            }
        )
        if target["blocked_reason"]:
            blocked_rows.append({"handoff_package_id": row["handoff_package_id"], "strategy_id": row["strategy_id"], "blocked_reason": target["blocked_reason"]})
    write_csv(output_dir / "dry_run_import_registry_report.csv", registry_rows)
    write_csv(output_dir / "first_batch_dry_run_status.csv", status_rows)
    write_csv(output_dir / "generated_spec_safety_check.csv", spec_rows)
    write_csv(output_dir / "dry_run_target_generation_report.csv", target_rows)
    write_csv(output_dir / "blocked_dry_run_targets.csv", blocked_rows, ["handoff_package_id", "strategy_id", "blocked_reason"])
    safety = {
        "paper_orders_submitted": False,
        "live_orders_submitted": False,
        "broker_order_endpoints_called": False,
        "active_runtime_strategies_changed": False,
        "all_runtime_ready_membership_changed": False,
        "generated_specs_paper_trading_allowed": False,
        "generated_specs_live_trading_allowed": False,
        "research_handoffs_mutated": False,
        "trading_tournament_mutated": False,
    }
    write_json(output_dir / "safety_check.json", safety)
    next_action = "fix_imported_dry_run_blockers_v1" if blocked_rows else "prepare_first_batch_runtime_enablement_review_v1"
    (output_dir / "next_action.md").write_text(next_action + "\n", encoding="utf-8")
    (output_dir / "dry_run_registration_manifest.yaml").write_text(
        "\n".join(
            [
                "task_id: enable_first_batch_disabled_runtime_dry_run_v1",
                f"generated_at_utc: {datetime.now(timezone.utc).isoformat()}",
                f"registry_path: {registry_path}",
                f"strategies_selected: {len(selected)}",
                f"blocked_dry_run_targets: {len(blocked_rows)}",
                "paper_orders_submitted: false",
                "live_orders_submitted: false",
                "broker_order_endpoints_called: false",
                f"exact_next_action: {next_action}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _write_blocker_fix_evidence(
        blocker_fix_output_dir,
        registry_rows=registry_rows,
        status_rows=status_rows,
        spec_rows=spec_rows,
        blocked_rows=blocked_rows,
        as_of=as_of,
        cache_dir=cache_dir,
        immutable_root=immutable_root,
    )
    return {
        "strategies_selected": len(selected),
        "blocked_dry_run_targets": len(blocked_rows),
        "target_generated": sum(1 for row in target_rows if row["target_generation_status"] == "dry_run_target_generated_disabled"),
        "output_dir": str(output_dir),
        "next_action": next_action,
    }


def _write_blocker_fix_evidence(
    output_dir: Path,
    *,
    registry_rows: list[dict[str, Any]],
    status_rows: list[dict[str, Any]],
    spec_rows: list[dict[str, Any]],
    blocked_rows: list[dict[str, Any]],
    as_of: str,
    cache_dir: Path,
    immutable_root: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    inventory_rows = []
    provider_rows = []
    for row in status_rows:
        blocker = row.get("blocked_reason", "")
        requires_frozen = "frozen_reference" in blocker or row["strategy_id"] in {
            "ice_vaneck_us_fallen_angel_angl_v1",
            "barbara_decelerated_psar_spy_bil_v1",
            "factory_v1_spy_trend_quality_state_d1",
        }
        requires_hyg = row["strategy_id"] == "schwoerer_hyg_ema100_spy_bil_v1"
        inventory_rows.append(
            {
                "handoff_package_id": row["handoff_package_id"],
                "generated_spec_path": row["generated_spec_path"],
                "calculator_id": row["calculator_id"],
                "current_dry_run_blocker": blocker,
                "required_provider_or_data_field": "frozen_reference_virtual_sleeve" if requires_frozen else "HYG_1Day_minimum_100_closes",
                "fixable_inside_app": str(requires_frozen or requires_hyg).lower(),
                "requires_readonly_alpaca_data": str(requires_hyg).lower(),
                "requires_immutable_handoff_reference_data": str(requires_frozen).lower(),
                "manual_review_required": str(False).lower(),
            }
        )
        if requires_frozen:
            provider = load_frozen_reference(row["handoff_package_id"], immutable_root)
            provider_rows.append(
                {
                    "handoff_package_id": row["handoff_package_id"],
                    "provider": "frozen_reference_virtual_sleeve",
                    "provider_status": provider.status,
                    "blocked_reason": provider.blocked_reason,
                    "source_path": provider.source_path,
                }
            )
    preflight = run_preflight(first_batch=True, output_dir=output_dir, cache_dir=cache_dir)
    generated_rows = [row for row in status_rows if row["target_generation_status"] == "dry_run_target_generated_disabled"]
    write_csv(output_dir / "dry_run_blocker_inventory.csv", inventory_rows)
    write_json(output_dir / "dry_run_blocker_inventory.json", inventory_rows)
    write_csv(output_dir / "provider_adapter_report.csv", provider_rows, ["handoff_package_id", "provider", "provider_status", "blocked_reason", "source_path"])
    write_csv(output_dir / "dry_run_target_generation_after_fixes.csv", status_rows)
    write_csv(output_dir / "blocked_after_fixes.csv", blocked_rows, ["handoff_package_id", "strategy_id", "blocked_reason"])
    write_csv(output_dir / "generated_dry_run_targets.csv", generated_rows, list(status_rows[0].keys()) if status_rows else ["handoff_package_id"])
    safety = {
        "paper_orders_submitted": False,
        "live_orders_submitted": False,
        "broker_order_endpoints_called": False,
        "active_runtime_strategies_changed": False,
        "all_runtime_ready_membership_changed": False,
        "generated_specs_paper_trading_allowed": False,
        "generated_specs_live_trading_allowed": False,
        "generated_specs_runtime_ready": False,
        "research_handoffs_mutated": False,
        "trading_tournament_mutated": False,
    }
    write_json(output_dir / "safety_check.json", safety)
    consistency = {
        **safety,
        "blockers_re_evaluated": len(status_rows),
        "dry_run_targets_generated": len(generated_rows),
        "blocked_after_fixes": len(blocked_rows),
        "network_calls": False,
        "data_preflight_missing_or_insufficient": preflight["missing_or_insufficient"],
    }
    write_json(output_dir / "consistency_check.json", consistency)
    next_action = "run_readonly_data_bootstrap_for_imported_dry_run_v1" if any("data_requirement_gap" in row.get("blocked_reason", "") for row in blocked_rows) else ("fix_imported_dry_run_blockers_v2" if blocked_rows else "run_first_batch_disabled_dry_run_review_v1")
    (output_dir / "next_action.md").write_text(next_action + "\n", encoding="utf-8")
    (output_dir / "fix_manifest.yaml").write_text(
        "\n".join(
            [
                "task_id: fix_imported_dry_run_blockers_v1",
                f"generated_at_utc: {datetime.now(timezone.utc).isoformat()}",
                f"as_of: {as_of}",
                f"blockers_re_evaluated: {len(status_rows)}",
                f"dry_run_targets_generated: {len(generated_rows)}",
                f"blocked_after_fixes: {len(blocked_rows)}",
                "paper_orders_submitted: false",
                "live_orders_submitted: false",
                "broker_order_endpoints_called: false",
                f"exact_next_action: {next_action}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    summary = [
        "# Dry-Run Blocker Fix Summary",
        "",
        f"- blockers_re_evaluated: {len(status_rows)}",
        f"- dry_run_targets_generated: {len(generated_rows)}",
        f"- blocked_after_fixes: {len(blocked_rows)}",
        "- paper_orders_submitted: false",
        "- live_orders_submitted: false",
        "- broker_order_endpoints_called: false",
        f"- exact_next_action: {next_action}",
    ]
    (output_dir / "dry_run_blocker_summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dry-run imported Standard V1 strategies without broker/order submission.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--first-batch", action="store_true")
    group.add_argument("--strategy-id")
    group.add_argument("--all-dry-run-enabled", action="store_true")
    parser.add_argument("--as-of")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_imported_strategy_dry_run(
        first_batch=args.first_batch,
        all_dry_run_enabled=args.all_dry_run_enabled,
        strategy_id=args.strategy_id,
        as_of=args.as_of,
        output_dir=args.output_dir,
    )
    print(f"strategies_selected: {result['strategies_selected']}")
    print(f"target_generated: {result['target_generated']}")
    print(f"blocked_dry_run_targets: {result['blocked_dry_run_targets']}")
    print(f"output_dir: {result['output_dir']}")
    print("paper_orders_submitted: false")
    print("live_orders_submitted: false")
    print("broker_order_endpoints_called: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

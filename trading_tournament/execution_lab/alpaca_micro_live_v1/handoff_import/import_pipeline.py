from __future__ import annotations

from pathlib import Path

from execution_lab.alpaca_micro_live_v1 import MODULE_ROOT, PACKAGE_ROOT
from execution_lab.alpaca_micro_live_v1.handoff_import.calculator_registry import CalculatorRegistry
from execution_lab.alpaca_micro_live_v1.handoff_import.compatibility import classify_package
from execution_lab.alpaca_micro_live_v1.handoff_import.conformance import run_conformance
from execution_lab.alpaca_micro_live_v1.handoff_import.contract_models import ImportResult
from execution_lab.alpaca_micro_live_v1.handoff_import.manifest_loader import load_handoff_package, write_immutable_cache
from execution_lab.alpaca_micro_live_v1.handoff_import.package_discovery import discover_package_dirs
from execution_lab.alpaca_micro_live_v1.handoff_import.provider_registry import ProviderRegistry
from execution_lab.alpaca_micro_live_v1.handoff_import.runtime_spec_generator import write_disabled_spec, write_import_registry

DEFAULT_HANDOFF_ROOT = PACKAGE_ROOT / "evidence" / "handoff_exports"
DEFAULT_AUDIT_ROOT = MODULE_ROOT / "evidence" / "runtime_audits" / "audit_alpaca_forward_observation_app_for_standard_handoff_import_v1" / "latest"
IMPORT_EVIDENCE_ROOT = MODULE_ROOT / "evidence" / "handoff_imports"
FIRST_BATCH = {
    "ice_vaneck_us_fallen_angel_angl_v1_standard_handoff_v1",
    "schwoerer_hyg_ema100_spy_bil_v1_standard_handoff_v1",
    "barbara_decelerated_psar_spy_bil_v1_standard_handoff_v1",
    "factory_v1_spy_trend_quality_state_d1_standard_handoff_v1",
}


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(MODULE_ROOT))
    except ValueError:
        return str(path)


def load_packages(handoff_root: Path = DEFAULT_HANDOFF_ROOT) -> list:
    return [load_handoff_package(path) for path in discover_package_dirs(handoff_root)]


def inventory_rows(packages: list) -> list[dict[str, str]]:
    rows = []
    for package in packages:
        rows.append({
            "package_id": package.package_id,
            "strategy_id": package.strategy_id,
            "family_id": package.family_id,
            "schema_id": package.schema_id,
            "package_version": package.package_version,
            "package_path": str(package.package_root),
            "manifest_path": str(package.manifest_path or ""),
            "contract_path": str(package.contract_path or ""),
            "fixture_path": str(package.fixture_path or ""),
            "calculator_type": package.calculator_type,
            "package_hash": package.package_hash,
            "classifications": ";".join(package.classifications),
        })
    return rows


def plan_rows(packages: list, calculators: CalculatorRegistry | None = None, providers: ProviderRegistry | None = None) -> list[dict[str, str]]:
    rows = []
    for package in packages:
        report = classify_package(package, calculators, providers)
        rows.append({
            "package_id": report.package_id,
            "strategy_id": report.strategy_id,
            "import_status": report.import_status,
            "calculator_status": report.calculator_status,
            "provider_status": report.provider_status,
            "conformance_status": report.conformance_status,
            "blocked_reasons": ";".join(report.blocked_reasons),
            "unsupported_reasons": ";".join(report.unsupported_reasons),
            "manual_review_reasons": ";".join(report.manual_review_reasons),
        })
    return rows


def run_import_pipeline(
    *,
    handoff_root: Path = DEFAULT_HANDOFF_ROOT,
    output_dir: Path = IMPORT_EVIDENCE_ROOT / "imports" / "latest",
    evidence_root: Path = IMPORT_EVIDENCE_ROOT,
    generated_spec_root: Path | None = None,
    all_found: bool = False,
    package_id: str | None = None,
    first_batch: bool = False,
    write_disabled_specs: bool = False,
    dry_run: bool = True,
) -> list[ImportResult]:
    packages = load_packages(handoff_root)
    if package_id:
        packages = [package for package in packages if package.package_id == package_id]
    elif first_batch:
        packages = [package for package in packages if package.package_id in FIRST_BATCH]
    elif not all_found:
        packages = []

    calculators = CalculatorRegistry()
    providers = ProviderRegistry()
    output_dir.mkdir(parents=True, exist_ok=True)
    conformance_dir = evidence_root / "conformance" / "latest"
    cache_root = evidence_root / "immutable_packages"
    results: list[ImportResult] = []
    registry_rows = []
    for package in packages:
        report = classify_package(package, calculators, providers)
        conformance = run_conformance(package, calculators, conformance_dir)
        report = report.__class__(
            package_id=report.package_id,
            strategy_id=report.strategy_id,
            import_status=report.import_status,
            calculator_status=report.calculator_status,
            provider_status=report.provider_status,
            conformance_status=conformance["status"],
            blocked_reasons=report.blocked_reasons,
            unsupported_reasons=report.unsupported_reasons,
            manual_review_reasons=report.manual_review_reasons,
        )
        spec_path = None
        cache_path = None
        if write_disabled_specs and not dry_run:
            cache_path = write_immutable_cache(package, cache_root)
            spec_path = write_disabled_spec(package, report, output_root=generated_spec_root) if generated_spec_root else write_disabled_spec(package, report)
            registry_rows.append({
                "strategy_id": package.strategy_id,
                "handoff_package_id": package.package_id,
                "enabled": False,
                "runtime_ready": False,
                "paper_trading_allowed": False,
                "live_trading_allowed": False,
                "blocked_reason": "pending_conformance_gate",
                "runtime_spec": _display_path(spec_path),
            })
        results.append(ImportResult(package, report, spec_path, cache_path, Path(conformance.get("report_path", "")) if conformance.get("report_path") else None))
    if write_disabled_specs and not dry_run:
        if generated_spec_root:
            write_import_registry(registry_rows, output_root=generated_spec_root)
        else:
            write_import_registry(registry_rows)
    return results

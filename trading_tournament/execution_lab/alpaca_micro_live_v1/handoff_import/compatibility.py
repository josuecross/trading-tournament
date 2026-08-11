from __future__ import annotations

from execution_lab.alpaca_micro_live_v1.handoff_import.calculator_registry import CalculatorRegistry
from execution_lab.alpaca_micro_live_v1.handoff_import.contract_models import CompatibilityReport, HandoffPackage
from execution_lab.alpaca_micro_live_v1.handoff_import.manifest_loader import validate_manifest_hashes
from execution_lab.alpaca_micro_live_v1.handoff_import.provider_registry import ProviderRegistry


def classify_package(package: HandoffPackage, calculators: CalculatorRegistry | None = None, providers: ProviderRegistry | None = None) -> CompatibilityReport:
    calculators = calculators or CalculatorRegistry()
    providers = providers or ProviderRegistry()
    blocked = list(package.classifications)
    unsupported: list[str] = []
    manual_review: list[str] = []
    blocked.extend(validate_manifest_hashes(package))

    calc_status = calculators.classify(package.calculator_type, package.strategy_id)
    if calc_status in {"calculator_binding_missing", "calculator_module_required"}:
        blocked.append(calc_status)
    if calc_status == "manual_review_required":
        manual_review.append("manual_review_required")

    provider_result = providers.classify(package.required_instruments, package.provider_requirements, package.required_data_fields)
    if provider_result.status == "provider_adapter_missing":
        blocked.extend(provider_result.missing)
    if provider_result.status == "unsupported_asset_class":
        blocked.extend(provider_result.missing)
        unsupported.extend(provider_result.unsupported)

    if "spdj" in package.package_id.lower() and "manual_review_required" not in manual_review:
        manual_review.append("manual_review_required")

    import_status = "importable_after_conformance"
    if unsupported:
        import_status = "unsupported"
    elif blocked or manual_review:
        import_status = "blocked"

    return CompatibilityReport(
        package_id=package.package_id,
        strategy_id=package.strategy_id,
        import_status=import_status,
        calculator_status=calc_status,
        provider_status=provider_result.status,
        conformance_status="not_run",
        blocked_reasons=sorted(set(blocked)),
        unsupported_reasons=sorted(set(unsupported)),
        manual_review_reasons=sorted(set(manual_review)),
    )

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import yaml

from .errors import StandardContractError
from .models import SCHEMA_ID, SCHEMA_VERSION, StandardHandoff


def sha256_file(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(item.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def normalized_standard_handoff_hash(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.setdefault("envelope", {})["package_content_hash"] = "__NORMALIZED_SELF_REFERENCE__"
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def normalized_spdj_package_hash(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        relative = item.relative_to(path).as_posix()
        content = item.read_bytes()
        if relative == "handoff_manifest.json":
            payload = json.loads(content.decode("utf-8"))
            payload["package_content_hash"] = "__NORMALIZED_SELF_REFERENCE__"
            content = (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(content)
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


@dataclass
class AdaptationResult:
    source_schema: str
    source_package_hash: str
    status: str
    normalized_handoff: StandardHandoff | None
    partial_mapping: dict[str, Any] = field(default_factory=dict)
    enrichment_gaps: list[dict[str, str]] = field(default_factory=list)
    integrity_status: str = "not_checked"
    fixture_status: str = "not_run"
    semantics_changed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_schema": self.source_schema,
            "source_package_hash": self.source_package_hash,
            "status": self.status,
            "normalized_handoff": None if self.normalized_handoff is None else self.normalized_handoff.to_dict(),
            "partial_mapping": self.partial_mapping,
            "enrichment_gaps": self.enrichment_gaps,
            "integrity_status": self.integrity_status,
            "fixture_status": self.fixture_status,
            "semantics_changed": self.semantics_changed,
        }


class SourceSchemaAdapter(Protocol):
    source_schema: str
    adapter_version: str

    def can_handle(self, package_path: Path) -> bool: ...

    def adapt(self, package_path: Path) -> AdaptationResult: ...


class StandardV1Adapter:
    source_schema = f"{SCHEMA_ID}:{SCHEMA_VERSION}"
    adapter_version = "standard_v1_adapter:1"

    def can_handle(self, package_path: Path) -> bool:
        manifest = package_path / "package_manifest.json"
        if not manifest.exists():
            return False
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        return payload.get("schema_id") == SCHEMA_ID

    def adapt(self, package_path: Path) -> AdaptationResult:
        manifest_path = package_path / "package_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if int(manifest.get("schema_version", -1)) != SCHEMA_VERSION:
            raise StandardContractError("unsupported_schema", "Unsupported standard package major version")
        files = manifest.get("files") or {}
        if not isinstance(files, dict) or "handoff.json" not in files:
            raise StandardContractError("package_integrity_failure", "Package manifest must hash handoff.json")
        for relative, expected in sorted(files.items()):
            path = package_path / relative
            actual = normalized_standard_handoff_hash(path) if relative == "handoff.json" and path.is_file() else sha256_file(path) if path.is_file() else "missing"
            if actual != expected:
                raise StandardContractError("package_integrity_failure", f"File hash mismatch: {relative}")
        logical_hash = _logical_standard_package_hash(files)
        if logical_hash != manifest.get("package_content_hash"):
            raise StandardContractError("package_integrity_failure", "Standard package logical hash mismatch")
        payload = json.loads((package_path / "handoff.json").read_text(encoding="utf-8"))
        if payload.get("envelope", {}).get("package_content_hash") != logical_hash:
            raise StandardContractError("package_integrity_failure", "Envelope package hash does not match package")
        handoff = StandardHandoff.from_dict(payload)
        return AdaptationResult(
            source_schema=self.source_schema,
            source_package_hash=logical_hash,
            status="contract_validated",
            normalized_handoff=handoff,
            integrity_status="package_validated",
            fixture_status="declared_not_run",
        )


class SpdjV1Adapter:
    source_schema = "spdj_forward_observation_handoff_schema_v1:v1"
    adapter_version = "spdj_to_standard_v1:1"

    def can_handle(self, package_path: Path) -> bool:
        path = package_path / "handoff_manifest.json"
        if not path.exists():
            return False
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload.get("package_schema_version") == "spdj_forward_observation_handoff_schema_v1"

    def adapt(self, package_path: Path) -> AdaptationResult:
        manifest = json.loads((package_path / "handoff_manifest.json").read_text(encoding="utf-8"))
        actual_hash = normalized_spdj_package_hash(package_path)
        if actual_hash != manifest.get("package_content_hash"):
            raise StandardContractError("package_integrity_failure", "SPDJ package content hash mismatch")
        contract = json.loads((package_path / "strategy_contract.json").read_text(encoding="utf-8"))
        signal = json.loads((package_path / "signal_contract.json").read_text(encoding="utf-8"))
        timing = json.loads((package_path / "schedule_and_timing_contract.json").read_text(encoding="utf-8"))
        fixtures = json.loads((package_path / "golden_fixture_manifest.json").read_text(encoding="utf-8"))
        claims = json.loads((package_path / "research_claims_and_nonclaims.json").read_text(encoding="utf-8"))
        caveats = []
        caveat_path = package_path / "caveat_register.csv"
        if caveat_path.exists():
            with caveat_path.open(newline="", encoding="utf-8") as handle:
                caveats = list(csv.DictReader(handle))

        mapping_by_symbol = {row["symbol"]: row["classification"] for row in contract["source_exposure_mappings"]}
        price_by_symbol = {row["symbol"]: row for row in contract["price_semantics"]["symbols"]}
        instruments = []
        for symbol in contract["symbols"]:
            mapping = mapping_by_symbol[symbol]
            instruments.append(
                {
                    "symbol": symbol,
                    "role": "risk_or_defensive_asset",
                    "exposure": mapping,
                    "substitution_policy": "exact_only" if mapping == "exact_match" else "approved_explicit_mapping",
                    "approved_mappings": [] if mapping == "exact_match" else [symbol],
                    "price_semantics": contract["price_semantics"]["research_semantics"],
                    "history_frequency": "monthly_total_return_from_adjusted_daily_history",
                    "minimum_history": int(contract["warmup"]["minimum_underlying_monthly_returns"]),
                    "lookback": int(contract["warmup"]["maximum_underlying_monthly_returns"]),
                }
            )
        source_hashes = dict(contract["hashes"])
        source_hashes.update({f"symbol_cache_{symbol}": row["cache_hash_reference"] for symbol, row in price_by_symbol.items()})
        research_claim = claims.get("research_claim") or claims.get("claim") or "research_eligible_dynamic_inflation_etf_portability_configuration"
        nonclaims = claims.get("explicit_nonclaims") or claims.get("nonclaims") or contract.get("explicit_nonclaims") or []
        eligibility_id = manifest.get("eligibility_evidence_hash")
        standard_payload = {
            "envelope": {
                "schema_id": SCHEMA_ID,
                "schema_version": SCHEMA_VERSION,
                "handoff_id": manifest["handoff_id"],
                "handoff_version": manifest["handoff_version"],
                "strategy_id": manifest["strategy_id"],
                "strategy_version": "v1",
                "family_id": manifest["family_id"],
                "architecture_id": manifest["architecture_id"],
                "canonical_trial_id": contract["canonical_trial_id"],
                "research_eligibility_status": manifest["research_eligibility_status"],
                "research_eligibility_evidence_id": eligibility_id,
                "created_at": manifest["created_at"],
                "package_content_hash": actual_hash,
                "source_hashes": source_hashes,
                "research_claim": research_claim,
                "explicit_nonclaims": nonclaims,
                "caveats": caveats,
            },
            "tradable_contract": {
                "instruments": instruments,
                "shorting_allowed": False,
                "leverage_allowed": False,
                "cash_behavior": "fully_invested_six_asset_target_no_cash_overlay",
                "target_normalization_rule": "fully_invested_long_only",
            },
            "signal_dependencies": [
                {
                    "signal_id": "spdj_cpi_yoy_point_in_time",
                    "signal_type": "external_release_signal",
                    "contract_version": signal["schema_version"],
                    "authority_provider_class": signal["statistical_authority"],
                    "series_dataset_id": signal["series_id"],
                    "point_in_time_required": True,
                    "publication_timing_required": True,
                    "frequency": "monthly_release_event",
                    "freshness_policy": {"cutoff": timing["CPI_regime_cutoff"], "late_event": "reject_or_diagnose_per_deployment"},
                    "missing_release_behavior": signal["no_release_behavior"]["state"],
                    "formula_configuration_reference": "signal_contract.json",
                },
                {
                    "signal_id": "spdj_etf_allocation_history",
                    "signal_type": "market_price_signal",
                    "contract_version": contract["price_semantics"]["schema_version"],
                    "authority_provider_class": "receiver_validated_adjusted_total_return_market_data",
                    "series_dataset_id": "SPY|IYR|GSG|GLD|AGG|TIP",
                    "point_in_time_required": False,
                    "publication_timing_required": False,
                    "frequency": "daily_to_monthly",
                    "freshness_policy": {"cutoff": timing["allocation_statistics_cutoff"]},
                    "missing_release_behavior": "block_calculation",
                    "formula_configuration_reference": "strategy_contract.json:target_algorithms",
                },
            ],
            "calculator_contract": {
                "calculator_type": "external_event_allocation",
                "calculator_contract_version": "spdj_dynamic_inflation_calculator_v1",
                "calculator_configuration": {
                    "signal_contract": signal,
                    "target_algorithms": contract["target_algorithms"],
                    "warmup": contract["warmup"],
                },
                "permitted_receiver_parameters": [],
            },
            "timing_contract": {
                "calendar_id": "XNYS",
                "calculation_information_cutoff": timing["allocation_statistics_cutoff"],
                "signal_availability_cutoff": timing["CPI_regime_cutoff"],
                "effective_rule": {"kind": "next_valid_session", "boundary": "after_close", "offset": 1},
                "no_event_behavior": "no_release_no_event_preserve_current_effective_target",
            },
            "required_fixture_types": [
                "signal_formula_fixture",
                "target_weight_fixture",
                "threshold_or_tie_fixture",
                "timing_fixture",
                "missing_event_fixture",
                "restart_fixture",
                "duplicate_event_fixture",
            ],
        }
        handoff = StandardHandoff.from_dict(standard_payload)
        return AdaptationResult(
            source_schema=self.source_schema,
            source_package_hash=actual_hash,
            status="contract_validated",
            normalized_handoff=handoff,
            integrity_status="package_validated",
            fixture_status=f"declared_{fixtures['fixture_count']}_not_executed",
        )


class InternalCaptureV1Adapter:
    source_schema = "legacy_internal_capture_handoff:1"
    adapter_version = "internal_capture_to_standard_v1:1"

    def can_handle(self, package_path: Path) -> bool:
        manifest_path = package_path / "handoff_manifest.yaml"
        if not manifest_path.exists():
            return False
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        return int(manifest.get("handoff_schema_version", -1)) == 1

    def adapt(self, package_path: Path) -> AdaptationResult:
        manifest = yaml.safe_load((package_path / "handoff_manifest.yaml").read_text(encoding="utf-8"))
        contract = json.loads((package_path / "strategy_handoff.json").read_text(encoding="utf-8"))
        validation = json.loads((package_path / "handoff_validation.json").read_text(encoding="utf-8"))
        if not all([validation.get("handoff_schema_valid"), validation.get("same_canonical_semantic_hash"), validation.get("fingerprint_matches_file")]):
            raise StandardContractError("package_integrity_failure", "Internal Capture semantic validation does not pass")
        frozen = contract["frozen_strategy"]
        partial = {
            "handoff_id": contract["identity"]["strategy_id"],
            "strategy_id": frozen["strategy_id"],
            "strategy_version": frozen["strategy_version"],
            "family_id": frozen["family_id"],
            "architecture_id": frozen["architecture_id"],
            "research_eligibility_status": contract["trading_tournament_eligibility_status"],
            "source_hashes": {"strategy_configuration": frozen["strategy_configuration_sha256"], "semantic_contract": validation["json_semantic_hash"]},
            "tradable_symbols": contract["data_contract"]["required_symbols"],
            "price_semantics": contract["data_contract"]["adjustment_convention"],
            "calculator_type": "rank_allocation",
            "calculator_configuration": {"formula": frozen["formula"], "parameters": frozen["parameters"], "target_rules": frozen["target_rules"]},
            "source_timing": {"signal_schedule": frozen["signal_schedule"], "execution_contract": contract["execution_contract"]},
        }
        gaps = [
            {"field": "created_at", "reason": "legacy handoff has no package creation timestamp"},
            {"field": "package_content_hash", "reason": "legacy package has semantic contract hash but no declared package hash algorithm"},
            {"field": "canonical_trial_id", "reason": "not carried in the handoff envelope"},
            {"field": "research_claim", "reason": "no canonical single research_claim field"},
            {"field": "calendar_id", "reason": "requires deterministic calendar but does not identify one"},
            {"field": "effective_timestamp_model", "reason": "following-session-close prose is not a resolved standard timing rule"},
            {"field": "fixture_manifest", "reason": "no standard golden timing/restart/duplicate fixture declaration"},
        ]
        return AdaptationResult(
            source_schema=self.source_schema,
            source_package_hash=sha256_path(package_path),
            status="standard_adapter_available_contract_enrichment_required",
            normalized_handoff=None,
            partial_mapping=partial,
            enrichment_gaps=gaps,
            integrity_status="semantic_contract_validated",
            fixture_status="not_declared",
        )


class SourceAdapterRegistry:
    def __init__(self, adapters: list[SourceSchemaAdapter] | None = None) -> None:
        self.adapters = adapters or [StandardV1Adapter(), SpdjV1Adapter(), InternalCaptureV1Adapter()]

    def identify(self, package_path: Path) -> SourceSchemaAdapter:
        matches = [adapter for adapter in self.adapters if adapter.can_handle(package_path)]
        if len(matches) != 1:
            raise StandardContractError(
                "unsupported_schema",
                "Package must match exactly one supported source schema",
                details={"match_count": len(matches)},
            )
        return matches[0]

    def inventory(self) -> list[dict[str, str]]:
        return [
            {"source_schema": adapter.source_schema, "adapter_version": adapter.adapter_version}
            for adapter in self.adapters
        ]


def _logical_standard_package_hash(files: dict[str, str]) -> str:
    encoded = json.dumps(files, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def standard_package_hash(files: dict[str, str]) -> str:
    return _logical_standard_package_hash(files)

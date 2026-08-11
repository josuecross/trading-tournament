from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .adapters import AdaptationResult, SourceAdapterRegistry
from .errors import StandardContractError
from .models import AcceptanceRecord, DeploymentProfile, IdentityBinding, SCHEMA_ID, SCHEMA_VERSION


IMPORTER_VERSION = "forward_observation_standard_importer_v1"


def importer_hash() -> str:
    return f"sha256:{hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}"


@dataclass
class ImportResult:
    adaptation: AdaptationResult
    acceptance: AcceptanceRecord
    identity_binding: IdentityBinding | None
    imported_path: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "adaptation": self.adaptation.to_dict(),
            "acceptance": self.acceptance.to_dict(),
            "identity_binding": None if self.identity_binding is None else self.identity_binding.__dict__,
            "imported_path": self.imported_path,
        }


class HandoffImporter:
    def __init__(self, *, storage_root: Path, registry: SourceAdapterRegistry | None = None) -> None:
        self.storage_root = storage_root
        self.registry = registry or SourceAdapterRegistry()

    def process(
        self,
        package_path: Path,
        *,
        mode: str,
        timestamp: str,
        receiver_strategy_id: str | None = None,
        strategy_instance_id: str | None = None,
        binding_provenance: str | None = None,
        deployment_profile: DeploymentProfile | None = None,
    ) -> ImportResult:
        if mode not in {"validate_only", "import_inactive"}:
            raise StandardContractError("missing_required_contract_field", f"Unsupported import mode: {mode}")
        adapter = self.registry.identify(package_path)
        adaptation = adapter.adapt(package_path)
        binding: IdentityBinding | None = None
        blocking = list(adaptation.enrichment_gaps)
        if adaptation.normalized_handoff and receiver_strategy_id:
            binding = IdentityBinding.create(
                handoff=adaptation.normalized_handoff,
                receiver_strategy_id=receiver_strategy_id,
                strategy_instance_id=strategy_instance_id or "",
                binding_timestamp=timestamp,
                binding_provenance=binding_provenance or "",
            )
        if deployment_profile:
            deployment_profile.validate(adaptation.normalized_handoff)
            if binding and (
                deployment_profile.receiver_strategy_id != binding.receiver_strategy_id
                or deployment_profile.strategy_instance_id != binding.strategy_instance_id
                or deployment_profile.handoff_id != binding.handoff_id
            ):
                raise StandardContractError("invalid_identity_binding", "Deployment profile does not match identity binding")
        if mode == "import_inactive" and (not adaptation.normalized_handoff or not binding or not deployment_profile):
            raise StandardContractError(
                "deployment_profile_missing",
                "Inactive import requires complete normalized contract, explicit identity binding, and deployment profile",
            )
        imported_path: str | None = None
        acceptance_status = "blocked" if blocking else "contract_validated"
        if mode == "import_inactive" and not blocking:
            destination = self.storage_root / adaptation.normalized_handoff.envelope.handoff_id / adaptation.source_package_hash.removeprefix("sha256:")
            if destination.exists():
                existing = json.loads((destination / "normalized_handoff.json").read_text(encoding="utf-8"))
                if existing != adaptation.normalized_handoff.to_dict():
                    raise StandardContractError("package_integrity_failure", "Immutable import destination contains different content")
            else:
                destination.mkdir(parents=True, exist_ok=False)
                (destination / "normalized_handoff.json").write_text(
                    json.dumps(adaptation.normalized_handoff.to_dict(), indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                (destination / "identity_binding.json").write_text(
                    json.dumps(binding.__dict__, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                (destination / "deployment_profile.json").write_text(
                    json.dumps(deployment_profile.to_dict(), indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
            imported_path = destination.as_posix()
            acceptance_status = "validated_not_active"
        acceptance = AcceptanceRecord(
            handoff_id=(adaptation.normalized_handoff.envelope.handoff_id if adaptation.normalized_handoff else adaptation.partial_mapping.get("handoff_id", "unresolved")),
            package_hash=adaptation.source_package_hash,
            source_schema=adaptation.source_schema,
            normalized_standard_schema=f"{SCHEMA_ID}:{SCHEMA_VERSION}",
            research_strategy_id=(adaptation.normalized_handoff.envelope.strategy_id if adaptation.normalized_handoff else adaptation.partial_mapping.get("strategy_id", "unresolved")),
            receiver_strategy_id=receiver_strategy_id,
            import_mode=mode,
            integrity_status=adaptation.integrity_status,
            contract_validation_status=("contract_validated" if adaptation.normalized_handoff else "contract_materialization_required"),
            fixture_validation_status=adaptation.fixture_status,
            deployment_profile_status=("validated_inactive" if deployment_profile else "not_supplied"),
            acceptance_status=acceptance_status,
            blocking_reasons=blocking,
            timestamp=timestamp,
            importer_version=IMPORTER_VERSION,
            importer_hash=importer_hash(),
            activation_performed=False,
        )
        if imported_path:
            Path(imported_path, "acceptance_record.json").write_text(
                json.dumps(acceptance.to_dict(), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        return ImportResult(adaptation, acceptance, binding, imported_path)

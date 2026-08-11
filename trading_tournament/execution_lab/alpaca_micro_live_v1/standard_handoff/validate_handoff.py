from __future__ import annotations

import argparse
import json
from pathlib import Path

from contracts.forward_observation.forward_observation_handoff_standard_v1.fixtures import FIXTURE_TYPES
from contracts.forward_observation.forward_observation_handoff_standard_v1.models import DeploymentProfile
from execution_lab.alpaca_micro_live_v1.standard_handoff import receiver_importer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate standardized forward-observation artifacts without activation.")
    parser.add_argument("action", choices=["validate-package", "normalize-package", "validate-deployment", "validate-fixtures"])
    parser.add_argument("--package", type=Path)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--fixtures", type=Path)
    parser.add_argument("--timestamp", default="1970-01-01T00:00:00Z")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.action in {"validate-package", "normalize-package"}:
        if args.package is None:
            raise SystemExit("--package is required")
        result = receiver_importer().process(args.package, mode="validate_only", timestamp=args.timestamp)
        payload = result.acceptance.to_dict() if args.action == "validate-package" else result.adaptation.to_dict()
    elif args.action == "validate-deployment":
        if args.profile is None:
            raise SystemExit("--profile is required")
        profile = DeploymentProfile(**json.loads(args.profile.read_text(encoding="utf-8")))
        profile.validate()
        payload = {"status": "deployment_profile_valid", "activation_performed": False}
    else:
        if args.fixtures is None:
            raise SystemExit("--fixtures is required")
        fixtures = json.loads(args.fixtures.read_text(encoding="utf-8"))
        unsupported = sorted({row.get("fixture_type") for row in fixtures} - FIXTURE_TYPES)
        payload = {"status": "fixture_definitions_valid" if not unsupported else "fixture_failure", "unsupported": unsupported}
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("status") != "fixture_failure" else 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json

from strategy_lab.research_os.research.fx_carry_external_family_evidence_aqr_currency_carry_v1 import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "evidence_id": result["evidence_id"],
                "family_id": result["family_id"],
                "relationship_to_active_source_page_strategy": result["relationship_to_active_source_page_strategy"],
                "evidence_dir": result["evidence_dir"],
                "first_valid_observation": result["first_valid_observation"],
                "last_valid_observation": result["last_valid_observation"],
                "valid_monthly_observations": result["valid_monthly_observations"],
                "source_version_sha256": result["source_version_sha256"],
                "extracted_sequence_sha256": result["extracted_sequence_sha256"],
                "consistency_passed": result["consistency_passed"],
                "exact_next_action": result["exact_next_action"],
            },
            indent=2,
            sort_keys=True,
        )
    )

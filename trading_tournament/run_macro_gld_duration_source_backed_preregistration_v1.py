from __future__ import annotations

import json

from strategy_lab.research_os.research.macro_gld_duration_source_backed_preregistration_v1 import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "family_id": result["family_id"],
                "outcome": result["outcome"],
                "preregistration_created": result["preregistration_created"],
                "prior_variant_fingerprint_count": result["prior_variant_fingerprint_count"],
                "exact_closed_variant_count": result["exact_closed_variant_count"],
                "relevant_source_count": result["relevant_source_count"],
                "consistency_passed": result["consistency_passed"],
                "next_action": result["next_action"],
            },
            indent=2,
            sort_keys=True,
        )
    )

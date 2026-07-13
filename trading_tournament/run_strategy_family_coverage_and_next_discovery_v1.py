from __future__ import annotations

import json

from strategy_lab.research_os.research.strategy_family_coverage_and_next_discovery_v1 import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "batch_id_reviewed": result["batch_id_reviewed"],
                "family_count": result["family_count"],
                "external_source_readiness_count": result["external_source_readiness_count"],
                "do_not_retest_count": result["do_not_retest_count"],
                "next_discovery_option_count": result["next_discovery_option_count"],
                "consistency_passed": result["consistency_passed"],
                "next_action": result["next_action"],
            },
            indent=2,
            sort_keys=True,
        )
    )

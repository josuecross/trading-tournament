from __future__ import annotations

import json

from strategy_lab.research_os.research.next_registry_candidate_bounded_design_after_regional_momentum import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "selected_candidate": result["selected_candidate"],
                "eligible_after_exclusions_count": result["eligible_after_exclusions_count"],
                "run_readiness_decision": result["run_readiness_decision"],
                "run_readiness_blocker": result["run_readiness_blocker"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )

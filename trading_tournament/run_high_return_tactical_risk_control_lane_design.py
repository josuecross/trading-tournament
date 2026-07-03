from __future__ import annotations

import json

from strategy_lab.research_os.research.high_return_tactical_risk_control_lane_design import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "lane_id": result["lane_id"],
                "variant_count_planned": result["variant_count_planned"],
                "risk_control_concepts_count": result["risk_control_concepts_count"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )

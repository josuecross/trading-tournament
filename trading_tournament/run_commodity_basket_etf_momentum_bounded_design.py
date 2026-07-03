from __future__ import annotations

import json

from strategy_lab.research_os.research.commodity_basket_etf_momentum_bounded_design import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "lane_id": result["lane_id"],
                "selected_task": result["selected_task"],
                "planned_row_count": result["planned_row_count"],
                "run_readiness_decision": result["run_readiness_decision"],
                "run_readiness_blocker": result["run_readiness_blocker"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )

from __future__ import annotations

import json

from strategy_lab.research_os.research.public_source_coppock_curve_bounded_bt_design import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "source_id": result["source_id"],
                "lane_id": result["lane_id"],
                "family_id": result["family_id"],
                "candidate_specific_evidence_valid": result["candidate_specific_evidence_valid"],
                "planned_row_count": result["planned_row_count"],
                "local_cache_complete": result["local_cache_complete"],
                "source_backed_parameters": result["source_backed_parameters"],
                "parameters_tuned": result["parameters_tuned"],
                "run_readiness_decision": result["run_readiness_decision"],
                "run_readiness_blocker": result["run_readiness_blocker"],
                "bounded_bt_lane_run": result["bounded_bt_lane_run"],
                "strategy_backtest_run": result["strategy_backtest_run"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )

from __future__ import annotations

import json

from strategy_lab.research_os.research.high_return_tactical_risk_control_lane_design_audit import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "lane_id_audited": result["lane_id_audited"],
                "variant_count_reviewed": result["variant_count_reviewed"],
                "thresholds_explicit": result["thresholds_explicit"],
                "local_cache_feasible": result["local_cache_feasible"],
                "run_readiness_decision": result["run_readiness_decision"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )

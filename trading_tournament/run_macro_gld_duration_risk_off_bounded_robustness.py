from __future__ import annotations

import json

from strategy_lab.research_os.research.macro_gld_duration_risk_off_bounded_robustness import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "lane_id": result["lane_id"],
                "rows_evaluated": result["rows_evaluated"],
                "rows_still_passing_under_10bps_stress": result["rows_still_passing_under_10bps_stress"],
                "rows_still_passing_under_25bps_stress": result["rows_still_passing_under_25bps_stress"],
                "rows_remain_interesting_after_robustness": result["rows_remain_interesting_after_robustness"],
                "robustness_evidence_usable": result["robustness_evidence_usable"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )

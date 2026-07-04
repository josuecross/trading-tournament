from __future__ import annotations

import json

from strategy_lab.research_os.research.regional_international_momentum_bounded_run import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "lane_id": result["lane_id"],
                "variant_count_evaluated": result["variant_count_evaluated"],
                "data_blocked_row_count": result["data_blocked_row_count"],
                "risk_control_rows_passed": result["risk_control_rows_passed"],
                "risk_control_rows_failed": result["risk_control_rows_failed"],
                "exposure_invariant_passed": result["exposure_invariant_passed"],
                "results_interpretable": result["results_interpretable"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )

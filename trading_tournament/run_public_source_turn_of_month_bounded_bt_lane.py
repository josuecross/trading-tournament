from __future__ import annotations

import json

from strategy_lab.research_os.research.public_source_turn_of_month_bounded_bt_run import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "lane_id": result["lane_id"],
                "variant_count_planned": result["variant_count_planned"],
                "variant_count_evaluated": result["variant_count_evaluated"],
                "primary_row_numeric_criteria_pass": result["primary_row_numeric_criteria_pass"],
                "timing_sanity_numeric_criteria_pass": result["timing_sanity_numeric_criteria_pass"],
                "invariant_failure_count": result["invariant_failure_count"],
                "results_interpretable": result["results_interpretable"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )

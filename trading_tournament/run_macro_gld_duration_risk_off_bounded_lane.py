from __future__ import annotations

import json

from strategy_lab.research_os.research.macro_gld_duration_risk_off_bounded_run import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "lane_id": result["lane_id"],
                "variant_count_evaluated": result["variant_count_evaluated"],
                "rows_passed_numeric_criteria": result["rows_passed_numeric_criteria"],
                "invariant_failure_count": result["invariant_failure_count"],
                "results_interpretable": result["results_interpretable"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )

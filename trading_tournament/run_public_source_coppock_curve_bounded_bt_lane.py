from __future__ import annotations

import json

from strategy_lab.research_os.research.public_source_coppock_curve_bounded_bt_run import run


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
                "sparse_signal_context_only": result["sparse_signal_context_only"],
                "completed_round_trip_event_count": result["completed_round_trip_event_count"],
                "invariant_failure_count": result["invariant_failure_count"],
                "results_interpretable": result["results_interpretable"],
                "usable_diagnostic_evidence": result["usable_diagnostic_evidence"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )

from __future__ import annotations

import json

from strategy_lab.research_os.research.public_source_percent_b_money_flow_state_reconciliation import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "source_id": result["source_id"],
                "lane_id": result["lane_id"],
                "chronology_decision": result["chronology_decision"],
                "current_percent_b_status": result["current_percent_b_status"],
                "variant_count_planned": result["variant_count_planned"],
                "variant_count_evaluated": result["variant_count_evaluated"],
                "primary_row_numeric_criteria_pass": result["primary_row_numeric_criteria_pass"],
                "primary_failure_reason": result["primary_failure_reason"],
                "exposure_invariant_passed": result["exposure_invariant_passed"],
                "queue_status_file_updated": result["queue_status_file_updated"],
                "current_authorized_next_action": result["current_authorized_next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )

from __future__ import annotations

import json

from strategy_lab.research_os.research.public_source_coppock_curve_final_state_reconciliation import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "source_id": result["source_id"],
                "lane_id": result["lane_id"],
                "final_coppock_curve_status": result["final_coppock_curve_status"],
                "final_status_locked": result["final_status_locked"],
                "completed_round_trip_event_count": result["completed_round_trip_event_count"],
                "primary_numeric_criteria_failed": result["primary_numeric_criteria_failed"],
                "primary_label": result["primary_label"],
                "queue_status_file_updated": result["queue_status_file_updated"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )

from __future__ import annotations

import json

from strategy_lab.research_os.research.public_source_larry_connors_rsi2_final_state_reconciliation import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "source_id": result["source_id"],
                "lane_id": result["lane_id"],
                "final_larry_connors_rsi2_status": result["final_larry_connors_rsi2_status"],
                "final_status_locked": result["final_status_locked"],
                "primary_robustness_label": result["primary_robustness_label"],
                "primary_10bps_stress_pass": result["primary_10bps_stress_pass"],
                "primary_25bps_stress_pass": result["primary_25bps_stress_pass"],
                "primary_rolling_window_weakness": result["primary_rolling_window_weakness"],
                "queue_status_file_updated": result["queue_status_file_updated"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )

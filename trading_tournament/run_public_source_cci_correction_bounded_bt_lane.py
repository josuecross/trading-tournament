from __future__ import annotations

import json

from strategy_lab.research_os.research.public_source_cci_correction_bounded_bt_run import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "source_id": result["source_id"],
                "lane_id": result["lane_id"],
                "family_id": result["family_id"],
                "variant_count_planned": result["variant_count_planned"],
                "variant_count_evaluated": result["variant_count_evaluated"],
                "data_blocked_row_count": result["data_blocked_row_count"],
                "weekly_observation_count": result["weekly_observation_count"],
                "daily_observation_count": result["daily_observation_count"],
                "entry_event_count": result["entry_event_count"],
                "exit_event_count": result["exit_event_count"],
                "primary_row_numeric_criteria_pass": result["primary_row_numeric_criteria_pass"],
                "exposure_invariant_passed": result["exposure_invariant_passed"],
                "results_interpretable": result["results_interpretable"],
                "usable_diagnostic_evidence": result["usable_diagnostic_evidence"],
                "bounded_bt_lane_run": result["public_source_cci_correction_bounded_bt_lane_run"],
                "provider_download": result["provider_download"],
                "intraday_data_used": result["intraday_data_used"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )

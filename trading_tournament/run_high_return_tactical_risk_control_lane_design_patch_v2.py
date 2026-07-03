from __future__ import annotations

import json

from strategy_lab.research_os.research.high_return_tactical_risk_control_lane_design_patch_v2 import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "lane_id": result["lane_id"],
                "variant_count_planned": result["variant_count_planned"],
                "volatility_input_explicit_after_patch_v2": result["volatility_input_explicit_after_patch_v2"],
                "drawdown_guard_timing_explicit_after_patch_v2": result["drawdown_guard_timing_explicit_after_patch_v2"],
                "controlled_equity_tracking_explicit": result["controlled_equity_tracking_explicit"],
                "baseline_mapping_complete_count": result["baseline_mapping_complete_count"],
                "baseline_mapping_missing_count": result["baseline_mapping_missing_count"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )

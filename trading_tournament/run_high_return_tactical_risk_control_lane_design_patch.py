from __future__ import annotations

import json

from strategy_lab.research_os.research.high_return_tactical_risk_control_lane_design_patch import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "lane_id": result["lane_id"],
                "variant_count_planned": result["variant_count_planned"],
                "all_variant_rules_explicit_after_patch": result["all_variant_rules_explicit_after_patch"],
                "thresholds_explicit_after_patch": result["thresholds_explicit_after_patch"],
                "fallback_rules_explicit_after_patch": result["fallback_rules_explicit_after_patch"],
                "reentry_rules_explicit_after_patch": result["reentry_rules_explicit_after_patch"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )

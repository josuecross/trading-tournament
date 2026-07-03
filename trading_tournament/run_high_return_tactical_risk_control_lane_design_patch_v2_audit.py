from __future__ import annotations

import json

from strategy_lab.research_os.research.high_return_tactical_risk_control_lane_design_patch_v2_audit import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "lane_id_audited": result["lane_id_audited"],
                "variant_count_reviewed": result["variant_count_reviewed"],
                "variant_table_valid": result["variant_table_valid"],
                "volatility_input_explicit": result["volatility_input_explicit"],
                "drawdown_guard_timing_explicit": result["drawdown_guard_timing_explicit"],
                "combined_rule_precedence_explicit": result["combined_rule_precedence_explicit"],
                "baseline_mapping_verified_count": result["baseline_mapping_verified_count"],
                "baseline_mapping_failed_count": result["baseline_mapping_failed_count"],
                "run_readiness_decision": result["run_readiness_decision"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )

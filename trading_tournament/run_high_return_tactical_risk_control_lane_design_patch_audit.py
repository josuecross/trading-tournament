from __future__ import annotations

import json

from strategy_lab.research_os.research.high_return_tactical_risk_control_lane_design_patch_audit import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "lane_id_audited": result["lane_id_audited"],
                "variant_table_valid": result["variant_table_valid"],
                "hidden_ambiguity_found": result["hidden_ambiguity_found"],
                "volatility_input_explicit": result["volatility_input_explicit"],
                "drawdown_guard_timing_explicit": result["drawdown_guard_timing_explicit"],
                "baseline_mapping_explicit": result["baseline_mapping_explicit"],
                "run_readiness_decision": result["run_readiness_decision"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )

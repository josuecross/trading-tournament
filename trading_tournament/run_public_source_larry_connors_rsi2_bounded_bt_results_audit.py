from __future__ import annotations

import json

from strategy_lab.research_os.research.public_source_larry_connors_rsi2_bounded_bt_results_audit import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "lane_id_audited": result["lane_id_audited"],
                "row_count_reviewed": result["row_count_reviewed"],
                "rsi_sma_formula_recomputed": result["rsi_sma_formula_recomputed"],
                "shifted_weight_no_lookahead_verified": result["shifted_weight_no_lookahead_verified"],
                "row_level_discrepancy_count": result["row_level_discrepancy_count"],
                "criteria_mismatch_count": result["criteria_mismatch_count"],
                "timing_sanity_context_only": result["timing_sanity_context_only"],
                "sample_adequacy_primary_classification": result["sample_adequacy_primary_classification"],
                "final_audit_decision": result["final_audit_decision"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )

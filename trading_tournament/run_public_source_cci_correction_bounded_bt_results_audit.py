from __future__ import annotations

import json

from strategy_lab.research_os.research.public_source_cci_correction_bounded_bt_results_audit import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "source_id": result["source_id"],
                "lane_id": result["lane_id"],
                "variant_count_reviewed": result["variant_count_reviewed"],
                "total_discrepancy_count": result["total_discrepancy_count"],
                "criteria_recomputation_passed": result["criteria_recomputation_passed"],
                "exposure_invariant_audit_passed": result["exposure_invariant_audit_passed"],
                "serious_interpretation_weakness": result["serious_interpretation_weakness"],
                "audit_decision": result["audit_decision"],
                "provider_download": result["provider_download"],
                "intraday_data_used": result["intraday_data_used"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )

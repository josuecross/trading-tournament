from __future__ import annotations

import json

from strategy_lab.research_os.research.public_source_cci_correction_final_state_reconciliation import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "source_id": result["source_id"],
                "lane_id": result["lane_id"],
                "final_status_locked": result["final_status_locked"],
                "final_cci_correction_status": result["final_cci_correction_status"],
                "results_audit_decision": result["results_audit_decision"],
                "serious_interpretation_weakness": result["serious_interpretation_weakness"],
                "queue_status_file_updated": result["queue_status_file_updated"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )

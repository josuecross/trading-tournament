from __future__ import annotations

import json

from strategy_lab.research_os.research.macro_gld_duration_risk_off_confirmation_report import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "lane_id": result["lane_id"],
                "rows_evaluated": result["rows_evaluated"],
                "rows_confirmed": result["rows_confirmed"],
                "rows_downgraded_to_context_only": result["rows_downgraded_to_context_only"],
                "rows_appear_diversifying_vs_active_combo": result["rows_appear_diversifying_vs_active_combo"],
                "confirmation_evidence_usable": result["confirmation_evidence_usable"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )

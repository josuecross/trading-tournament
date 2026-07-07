from __future__ import annotations

import json

from strategy_lab.research_os.research.public_source_macd_stochastic_intake_state_reconciliation import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "source_id": result["source_id"],
                "final_status_locked": result["final_status_locked"],
                "final_macd_stochastic_status": result["final_macd_stochastic_status"],
                "single_source_intake_decision": result["single_source_intake_decision"],
                "batch_intake_decision": result["batch_intake_decision"],
                "exit_rule_not_source_backed_enough_to_freeze": result[
                    "exit_rule_not_source_backed_enough_to_freeze"
                ],
                "indicator_defaults_interval_flexibility": result["indicator_defaults_interval_flexibility"],
                "queue_status_file_updated": result["queue_status_file_updated"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )

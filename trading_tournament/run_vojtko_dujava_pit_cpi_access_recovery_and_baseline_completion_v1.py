from __future__ import annotations

import json

from strategy_lab.research_os.research.vojtko_dujava_pit_cpi_access_recovery_and_baseline_completion_v1 import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "task_id": result["task_id"],
                "strategy_id": result["strategy_id"],
                "outcome": result["outcome"],
                "blocker": result["blocker"],
                "baseline_implemented": result["baseline_implemented"],
                "alfred_access_status": result["alfred_access_status"],
                "alfred_observation_count": result["alfred_observation_count"],
                "fixed_bls_anchor_loaded_count": result["fixed_bls_anchor_loaded_count"],
                "fixed_bls_anchor_count": result["fixed_bls_anchor_count"],
                "point_in_time_signal_gate_passed": result["point_in_time_signal_gate_passed"],
                "prior_packet_preserved_unchanged": result["prior_packet_preserved_unchanged"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
            sort_keys=True,
        )
    )

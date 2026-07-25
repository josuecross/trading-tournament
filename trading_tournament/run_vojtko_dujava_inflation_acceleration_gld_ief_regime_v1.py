from __future__ import annotations

import json

from strategy_lab.research_os.research.vojtko_dujava_inflation_acceleration_gld_ief_regime_v1 import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "strategy_id": result["strategy_id"],
                "family_id": result["family_id"],
                "outcome": result["outcome"],
                "baseline_implemented": result["baseline_implemented"],
                "cpi_observation_count": result.get("cpi_observation_count", 0),
                "regime_switch_count": result.get("regime_switch_count", 0),
                "exposure_invariant_passed": result.get("exposure_invariant_passed", False),
                "identity_overlay_equality_passed": result.get("identity_overlay_equality_passed", False),
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
            sort_keys=True,
        )
    )

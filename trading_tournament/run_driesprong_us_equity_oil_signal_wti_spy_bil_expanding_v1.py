from __future__ import annotations

import json

from strategy_lab.research_os.research.driesprong_us_equity_oil_signal_wti_spy_bil_expanding_v1 import run


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
                "signal_month_count": result.get("signal_month_count", 0),
                "transaction_count": result.get("transaction_count", 0),
                "exposure_invariant_passed": result.get("exposure_invariant_passed", False),
                "identity_overlay_equality_passed": result.get("identity_overlay_equality_passed", False),
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
            sort_keys=True,
        )
    )

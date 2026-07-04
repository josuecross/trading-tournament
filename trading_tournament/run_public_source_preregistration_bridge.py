from __future__ import annotations

import json

from strategy_lab.research_os.research.public_source_preregistration_bridge import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "blank_intake_eligibility_decision": result["blank_intake_eligibility_decision"],
                "family_similarity_group_count": result["family_similarity_group_count"],
                "bt_control_poc_passed": result["bt_control_poc_passed"],
                "bt_multasset_poc_passed": result["bt_multasset_poc_passed"],
                "public_strategy_selected": result["public_strategy_selected"],
                "public_strategy_implemented": result["public_strategy_implemented"],
                "strategy_backtest_run": result["strategy_backtest_run"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )

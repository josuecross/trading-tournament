from __future__ import annotations

import json

from strategy_lab.research_os.research.public_source_plus_python_strategy_library_feasibility import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "bt_feasibility_decision": result["bt_feasibility_decision"],
                "bt_package_available_now": result["bt_package_available_now"],
                "bt_immediate_poc_dependency_blocker": result["bt_immediate_poc_dependency_blocker"],
                "package_install_attempted": result["package_install_attempted"],
                "strategy_implemented": result["strategy_implemented"],
                "strategy_backtest_run": result["strategy_backtest_run"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )

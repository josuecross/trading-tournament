from __future__ import annotations

import json

from strategy_lab.research_os.research.bt_adapter_control_poc import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "bt_package_available": result["bt_package_available"],
                "bt_package_version": result["bt_package_version"],
                "adapter_execution_attempted": result["adapter_execution_attempted"],
                "reference_comparison_performed": result["reference_comparison_performed"],
                "exposure_invariant_passed": result["exposure_invariant_passed"],
                "final_adapter_decision": result["final_adapter_decision"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )

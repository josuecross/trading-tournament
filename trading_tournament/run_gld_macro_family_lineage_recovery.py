from __future__ import annotations

import json

from strategy_lab.research_os.research.gld_macro_family_lineage_recovery import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "selected_task": result["selected_task"],
                "selected_family": result["selected_family"],
                "macro_rows_recovered_count": result["macro_rows_recovered_count"],
                "usable_diagnostic_evidence": result["usable_diagnostic_evidence"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )

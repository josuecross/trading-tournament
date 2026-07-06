from __future__ import annotations

import json

from strategy_lab.research_os.research.backtest_sample_adequacy_report import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "included_row_count": result["included_row_count"],
                "run_evidence_paths_inspected_count": result["run_evidence_paths_inspected_count"],
                "missing_run_evidence_count": result["missing_run_evidence_count"],
                "classification_counts": result["classification_counts"],
                "new_backtests_run": result["new_backtests_run"],
                "provider_download": result["provider_download"],
                "intraday_data_used": result["intraday_data_used"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )

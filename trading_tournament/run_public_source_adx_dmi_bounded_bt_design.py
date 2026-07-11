from __future__ import annotations

import json

from strategy_lab.research_os.research.public_source_adx_dmi_bounded_bt_design import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "source_id": result["source_id"],
                "lane_id": result["lane_id"],
                "family_id": result["family_id"],
                "planned_row_count": result["planned_row_count"],
                "source_backed_parameters": result["source_backed_parameters"],
                "parameters_tuned": result["parameters_tuned"],
                "formula_contract_complete": result["formula_contract_complete"],
                "canonical_adx_dmi_utility_found": result["canonical_adx_dmi_utility_found"],
                "first_valid_di_date": result["first_valid_di_date"],
                "first_valid_adx_date": result["first_valid_adx_date"],
                "effective_start_date_after_alignment_and_warmup": result[
                    "effective_start_date_after_alignment_and_warmup"
                ],
                "similarity_hit_count": result["similarity_hit_count"],
                "duplicate_or_do_not_retest_blocker": result["duplicate_or_do_not_retest_blocker"],
                "local_cache_complete": result["local_cache_complete"],
                "spy_ohlc_cache_ready": result["spy_ohlc_cache_ready"],
                "run_readiness_decision": result["run_readiness_decision"],
                "run_readiness_blocker": result["run_readiness_blocker"],
                "bounded_bt_lane_run": result["bounded_bt_lane_run"],
                "strategy_backtest_run": result["strategy_backtest_run"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
        )
    )

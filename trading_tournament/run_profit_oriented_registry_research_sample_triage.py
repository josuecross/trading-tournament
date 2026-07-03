import json

from strategy_lab.research_os.research.profit_oriented_registry_research_sample_triage import run


if __name__ == "__main__":
    result = run()
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "total_research_sample_review_rows_inspected": result[
                    "total_research_sample_review_rows_inspected"
                ],
                "rows_excluded": result["rows_excluded"],
                "rows_eligible_after_filters": result["rows_eligible_after_filters"],
                "clear_winner_found": result["clear_winner_found"],
                "selected_strategy_id": result["selected_strategy_id"],
                "selected_family": result["selected_family"],
                "next_action": result["next_action"],
                "consistency_passed": result["consistency_passed"],
            },
            indent=2,
            sort_keys=True,
        )
    )

from strategy_lab.research_os.research.profit_research_batch_v1_labeling_fix import run


if __name__ == "__main__":
    result = run()
    print(f"labeling_fix_output={result['output_dir']}")
    print(f"batch_id_fixed={result['batch_id_fixed']}")
    print(f"underlabeled_before={result['high_return_severe_drawdown_underlabeled_count_before']}")
    print(f"underlabeled_after={result['high_return_severe_drawdown_underlabeled_count_after']}")
    print(f"favorable_zero_drawdown_before={result['favorable_zero_drawdown_score_label_count_before']}")
    print(f"favorable_zero_drawdown_after={result['favorable_zero_drawdown_score_label_count_after']}")
    print(f"invalid_diversifier_label_count_after={result['invalid_diversifier_label_count_after']}")
    print(f"macro_gld_lineage_preserved={result['macro_gld_lineage_preserved']}")
    print(f"deeper_research_family_count_after_label_fix={result['deeper_research_family_count_after_label_fix']}")
    print(f"next_action={result['next_action']}")
    print(f"consistency_passed={result['consistency_passed']}")

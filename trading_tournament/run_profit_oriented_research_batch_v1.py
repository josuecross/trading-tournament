from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import run


if __name__ == "__main__":
    result = run()
    print(f"observation_delegation_output={result['observation_output_dir']}")
    print(f"profit_research_batch_output={result['research_output_dir']}")
    print(f"batch_id={result['batch_id']}")
    print(f"variants_evaluated_count={result['variants_evaluated_count']}")
    print(f"families_evaluated_count={result['families_evaluated_count']}")
    print(f"next_action={result['next_action']}")
    print(f"consistency_passed={result['consistency_passed']}")

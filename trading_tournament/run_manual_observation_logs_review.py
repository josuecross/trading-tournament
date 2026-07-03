from strategy_lab.research_os.operations.manual_observation_logs_review import run


if __name__ == "__main__":
    result = run()
    print(f"observation_logs_review_output={result['output_dir']}")
    print(f"placeholder_snapshots_created={result['placeholder_snapshots_created']}")
    print(f"next_action={result['next_action']}")
    print(f"consistency_passed={result['consistency_passed']}")

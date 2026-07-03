from strategy_lab.research_os.operations.observation_checkpoint import run


if __name__ == "__main__":
    result = run()
    print(f"observation_only_output={result['output_dir']}")
    print(f"observation_logs_status={result['observation_logs_status']}")
    print(f"next_action={result['next_action']}")
    print(f"consistency_passed={result['consistency_passed']}")

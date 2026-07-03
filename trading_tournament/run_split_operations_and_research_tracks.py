from strategy_lab.research_os.split_tracks import run


if __name__ == "__main__":
    result = run()
    print(f"split_tracks_output={result['output_dir']}")
    print(f"next_action={result['next_action']}")
    print(f"consistency_passed={result['consistency_passed']}")

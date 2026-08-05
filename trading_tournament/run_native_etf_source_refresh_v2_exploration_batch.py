import json

from strategy_lab.research_os.research.native_etf_source_refresh_v2_exploration_batch import (
    run,
)


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["overall_pass"] else 1)

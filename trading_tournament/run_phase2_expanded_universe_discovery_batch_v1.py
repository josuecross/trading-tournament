import json

from strategy_lab.research_os.research.phase2_expanded_universe_discovery_batch_v1 import run


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))

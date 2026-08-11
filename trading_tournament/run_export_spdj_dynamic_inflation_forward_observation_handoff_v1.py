import json

from strategy_lab.research_os.research.export_spdj_dynamic_inflation_forward_observation_handoff_v1 import run


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))

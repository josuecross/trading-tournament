import json

from strategy_lab.research_os.research.run_spdj_dynamic_inflation_robustness_v1 import run


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))

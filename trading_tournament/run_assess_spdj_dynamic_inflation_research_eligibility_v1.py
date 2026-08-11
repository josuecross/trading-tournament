import json

from strategy_lab.research_os.research.assess_spdj_dynamic_inflation_research_eligibility_v1 import run


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))

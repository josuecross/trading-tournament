import json

from strategy_lab.research_os.research.resolve_refreeze_spdj_dynamic_inflation_signal_contract_v2 import run


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))

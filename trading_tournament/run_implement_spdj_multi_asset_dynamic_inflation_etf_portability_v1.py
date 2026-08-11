import json

from strategy_lab.research_os.research.implement_spdj_multi_asset_dynamic_inflation_etf_portability_v1 import run


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))

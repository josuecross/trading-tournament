from __future__ import annotations

import json
from pathlib import Path

from strategy_lab.research_os.research.resume_bounded_multi_asset_universe_data_readiness_v1 import run


if __name__ == "__main__":
    print(json.dumps(run(Path.cwd()), indent=2, sort_keys=True))

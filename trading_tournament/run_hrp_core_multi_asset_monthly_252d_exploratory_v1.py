from __future__ import annotations

from pathlib import Path

from strategy_lab.research_os.research import hrp_core_multi_asset_monthly_252d_exploratory_v1 as exploratory


if __name__ == "__main__":
    result = exploratory.run(Path(__file__).resolve().parent)
    print(f"classification={result['classification']}")
    print(f"artifact_dir={result['artifact_dir']}")

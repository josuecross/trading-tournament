from __future__ import annotations

from pathlib import Path

from strategy_lab.research_os.research import tom_international_country_etf_tbill_switch_exploratory_v1 as exploratory


if __name__ == "__main__":
    result = exploratory.run(Path(__file__).resolve().parent)
    print(f"classification={result['classification']}")
    print(f"trial_count={result['trial_count']}")
    print(f"completed_trial_count={result['completed_trial_count']}")
    print(f"failed_trial_count={result['failed_trial_count']}")
    print(f"artifact_dir={result['artifact_dir']}")

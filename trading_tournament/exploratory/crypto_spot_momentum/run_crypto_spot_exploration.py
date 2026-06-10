from __future__ import annotations

import argparse
import sys
from pathlib import Path


if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from exploratory.crypto_spot_momentum.crypto_validation import run_exploration  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Tier 1 crypto spot momentum exploratory screening.")
    parser.add_argument("--mode", choices=["smoke", "research_sample", "candidate_exhaustive"], default="research_sample")
    parser.add_argument("--source", choices=["yfinance", "ccxt"], default="yfinance")
    parser.add_argument("--no-network", action="store_true")
    parser.add_argument("--reuse-cache", action="store_true", default=True)
    parser.add_argument("--force-download", action="store_true")
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument(
        "--config",
        default=str(Path(__file__).resolve().parent / "config.yaml"),
        help="Path to crypto exploratory config.yaml.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_exploration(
        config_path=Path(args.config),
        mode=args.mode,
        source=args.source,
        no_network=args.no_network,
        reuse_cache=args.reuse_cache,
        force_download=args.force_download,
        max_workers=args.max_workers,
    )
    print(f"status={result['status']}")
    print(f"latest_dir={result['latest_dir']}")
    print(f"network_download_occurred={result.get('network_download_occurred', False)}")
    if result["status"] != "complete":
        print(f"reason={result.get('reason', '')}")
        return 2
    strategy_results = result.get("strategy_results")
    if strategy_results is not None and not strategy_results.empty:
        standard = strategy_results[strategy_results["slippage_label"] == "standard"]
        if not standard.empty:
            best = standard.sort_values("final_equity", ascending=False).iloc[0]
            print(f"best_standard_strategy={best['strategy']}")
            print(f"best_standard_final_equity={best['final_equity']:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

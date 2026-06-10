from __future__ import annotations

from pathlib import Path

from src.reporting import regenerate_report_from_latest


ROOT = Path(__file__).resolve().parent


def main() -> int:
    latest = ROOT / "results" / "latest"
    if latest.exists():
        run_dir = latest
    else:
        runs = sorted((ROOT / "results" / "runs").glob("*"))
        if not runs:
            raise SystemExit("No run directory found. Run python3 run_backtest.py first.")
        run_dir = runs[-1]
    regenerate_report_from_latest(run_dir)
    print(f"Report regenerated: {run_dir / 'summary_report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

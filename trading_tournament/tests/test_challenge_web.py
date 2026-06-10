from __future__ import annotations

import csv
import zipfile
from pathlib import Path

import yaml

from run_challenge_web import HTML_PAGE, build_runner_command, elapsed_time_seconds, latest_artifacts_summary


def test_build_runner_command_research_sample_minimal_flags() -> None:
    command = build_runner_command(
        {
            "mode": "research_sample",
            "include_etf": True,
            "include_benchmarks": True,
            "include_crypto": True,
            "include_leverage": False,
            "reuse_cache": True,
            "no_network": True,
            "max_runtime_minutes": 12,
        },
        python_executable="/tmp/python",
        repo_root=Path("/repo"),
    )
    assert command[:3] == ["/tmp/python", "/repo/run_challenge_audit.py", "--mode"]
    assert "research_sample" in command
    assert "--include-etf" in command
    assert "--include-benchmarks" in command
    assert "--include-crypto" in command
    assert "--no-leverage" in command
    assert "--reuse-cache" in command
    assert "--no-network" in command
    assert command[-2:] == ["--max-runtime-minutes", "12"]


def test_build_runner_command_candidate_defaults_finalist_and_excludes_selected_lanes() -> None:
    command = build_runner_command(
        {
            "mode": "candidate_exhaustive",
            "include_etf": True,
            "include_benchmarks": True,
            "include_crypto": False,
            "include_leverage": False,
        },
        python_executable="/tmp/python",
        repo_root=Path("/repo"),
    )
    assert "--finalists" in command
    assert command[command.index("--finalists") + 1] == "current_no_cash_proxy_alpha_AB"
    assert "--no-crypto" in command
    assert "--no-leverage" in command


def test_build_runner_command_rejects_bad_mode() -> None:
    try:
        build_runner_command({"mode": "nightly_full_exhaustive"}, python_executable="/tmp/python", repo_root=Path("/repo"))
    except ValueError as exc:
        assert "Unsupported mode" in str(exc)
    else:
        raise AssertionError("bad mode was accepted")


def test_build_runner_command_rejects_unsafe_finalist() -> None:
    try:
        build_runner_command(
            {"mode": "candidate_exhaustive", "finalists": "current;rm -rf"},
            python_executable="/tmp/python",
            repo_root=Path("/repo"),
        )
    except ValueError as exc:
        assert "Finalists may only contain" in str(exc)
    else:
        raise AssertionError("unsafe finalist was accepted")


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_latest_artifacts_summary_reads_compact_evidence(tmp_path: Path) -> None:
    latest = tmp_path / "evidence" / "challenge_runs" / "latest"
    latest.mkdir(parents=True)
    (latest / "assumptions_and_costs.yaml").write_text(
        yaml.safe_dump(
            {
                "validation": {"mode": "research_sample", "final_validation_completed": False},
                "lanes": {"include_etf": True, "include_crypto": False},
            }
        ),
        encoding="utf-8",
    )
    write_csv(
        latest / "challenge_results.csv",
        [{"run_id": "run_1", "strategy": "current_no_cash_proxy_alpha_AB"}],
    )
    write_csv(
        latest / "rolling_window_summary.csv",
        [
            {
                "strategy": "current_no_cash_proxy_alpha_AB",
                "standard_or_stress": "standard",
                "horizon": 90,
                "pct_target_300_before_stop": 0.12,
                "pct_target_400_before_stop": 0.03,
                "pct_any_project_stop_hit": 0.01,
                "rolling_method": "deterministic_sample",
                "number_of_windows": 10,
                "possible_window_count": 100,
                "sampled_results_are_final": False,
            }
        ],
    )
    write_csv(
        latest / "strategy_rankings.csv",
        [{"rank_overall": 1, "strategy": "current_no_cash_proxy_alpha_AB", "audit_verdict": "watchlist"}],
    )
    (latest / "challenge_summary.md").write_text("summary", encoding="utf-8")
    zip_path = tmp_path / "evidence" / "challenge_runs" / "latest_challenge_packet.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("challenge_summary.md", "summary")

    summary = latest_artifacts_summary(tmp_path)
    assert summary["exists"] is True
    assert summary["run_id"] == "run_1"
    assert summary["zip_exists"] is True
    assert summary["validation"]["mode"] == "research_sample"
    assert summary["comparison_90d"][0]["strategy"] == "current_no_cash_proxy_alpha_AB"


def test_elapsed_time_seconds_uses_finished_or_current_time() -> None:
    assert elapsed_time_seconds("2026-05-31T10:00:00+00:00", "2026-05-31T10:02:05+00:00") == 125
    assert elapsed_time_seconds("", "") == 0


def test_page_includes_running_animation_and_elapsed_timer() -> None:
    assert 'id="progress"' in HTML_PAGE
    assert 'id="elapsed"' in HTML_PAGE
    assert "@keyframes spin" in HTML_PAGE
    assert "@keyframes slide" in HTML_PAGE
    assert "Elapsed" in HTML_PAGE

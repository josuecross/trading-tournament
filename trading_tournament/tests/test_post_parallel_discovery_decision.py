from __future__ import annotations

import json
from pathlib import Path

import yaml

import run_post_parallel_discovery_decision as decision


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def seed_parallel_outputs(root: Path) -> None:
    latest = root / decision.PARALLEL_DIR
    write(
        latest / "parallel_research_discovery_summary.md",
        "# Parallel Research Discovery\n\nBest family: `gtaa_faber_style_benchmark_lane`\n",
    )
    write(
        latest / "family_leaderboard.csv",
        "\n".join(
            [
                "family_id,family_verdict,best_score,best_strategy_id,missing_symbols",
                "gtaa_faber_style_benchmark_lane,watchlist_family,56.76,gtaa_top3_trend_filter_v1,",
                "static_all_weather_or_permanent_portfolio_benchmark,watchlist_family,49.79,static_all_weather_trend_filtered_v1,",
            ]
        )
        + "\n",
    )
    write(
        latest / "strategy_leaderboard.csv",
        "\n".join(
            [
                "family_id,strategy_id,profit_first_score,score_label,strategy_verdict",
                "gtaa_faber_style_benchmark_lane,gtaa_top3_trend_filter_v1,56.76,watchlist,watchlist",
                "gtaa_faber_style_benchmark_lane,gtaa_breadth_defensive_v1,54.94,watchlist,watchlist",
                "gtaa_faber_style_benchmark_lane,gtaa_equal_weight_trend_filter_v1,47.31,watchlist,watchlist",
                "gtaa_faber_style_benchmark_lane,gtaa_spy_gld_ief_static_trend_v1,48.17,watchlist,watchlist",
                "gtaa_faber_style_benchmark_lane,gtaa_top2_risk_adjusted_v1,24.79,weak,too_risky",
            ]
        )
        + "\n",
    )
    write(latest / "promotion_review_candidates.csv", "family_id,strategy_id,profit_first_score,score_label,strategy_verdict\n")
    write(
        latest / "watchlist_rows.csv",
        "\n".join(
            [
                "family_id,strategy_id,profit_first_score,score_label,strategy_verdict",
                "gtaa_faber_style_benchmark_lane,gtaa_top3_trend_filter_v1,56.76,watchlist,watchlist",
            ]
        )
        + "\n",
    )
    write(
        latest / "too_risky_rows.csv",
        "\n".join(
            [
                "family_id,strategy_id,profit_first_score,score_label,strategy_verdict",
                "gtaa_faber_style_benchmark_lane,gtaa_top2_risk_adjusted_v1,24.79,weak,too_risky",
            ]
        )
        + "\n",
    )
    write(latest / "rejected_rows.csv", "family_id,strategy_id,profit_first_score,score_label,strategy_verdict\n")
    write(latest / "next_action.md", "# Next Action\n\n`continue_best_parallel_discovery_family`\n")
    write(
        latest / "parallel_research_discovery_consistency_check.json",
        json.dumps({"no_candidate_exhaustive_run": True, "no_paper_forward_activation": True, "consistency_passed": True}),
    )


def seed_registry(root: Path) -> None:
    rows = []
    for row_id, active in [
        ("current_no_cash_proxy_alpha_AB", True),
        ("paper_forward_vm_quality_lowvol_proxy_v1", True),
        ("paper_forward_dsr_sector_equal_weight_defensive_filter_v1", True),
        ("SPY_200d_trend_model", True),
    ]:
        rows.append(
            {
                "id": row_id,
                "rules_frozen": True,
                "paper_forward_active": active,
                "allowed_next_action": "observe_only",
                "candidate_exhaustive_run": False,
            }
        )
    rows.append(
        {
            "id": "dsr_sector_top2_momentum_200d_bil_v1",
            "status": "future_review_candidate",
            "promotion_review_required": True,
            "candidate_exhaustive_run": False,
            "paper_forward_active": False,
        }
    )
    path = root / decision.REGISTRY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"strategies": rows}, sort_keys=False), encoding="utf-8")


def test_reads_parallel_outputs_and_confirms_no_promotion_candidates(tmp_path: Path, monkeypatch) -> None:
    seed_parallel_outputs(tmp_path)
    seed_registry(tmp_path)
    evidence = decision.read_parallel_evidence(tmp_path)
    confirmations = decision.confirm_parallel_state(evidence, tmp_path)
    assert confirmations["no_promotion_candidates_exist"] is True
    assert confirmations["gtaa_top3_is_watchlist"] is True

    monkeypatch.setattr(decision, "parallel_discovery_committed", lambda root: True)
    result = decision.run_post_parallel_discovery_decision(tmp_path)
    latest = Path(result["output_dir"])
    consistency = json.loads((latest / "post_parallel_discovery_consistency_check.json").read_text(encoding="utf-8"))
    assert result["decision"] == decision.FINAL_DECISION
    assert consistency["no_new_research_run"] is True
    assert consistency["no_backtest_run"] is True
    assert consistency["no_data_download"] is True
    assert consistency["no_provider_api_call"] is True
    assert consistency["consistency_passed"] is True
    assert (latest / "post_parallel_discovery_decision_packet.zip").exists()


def test_uncommitted_parallel_outputs_choose_commit_first(tmp_path: Path, monkeypatch) -> None:
    seed_parallel_outputs(tmp_path)
    seed_registry(tmp_path)
    monkeypatch.setattr(decision, "parallel_discovery_committed", lambda root: False)
    result = decision.run_post_parallel_discovery_decision(tmp_path)
    assert result["decision"] == decision.COMMIT_FIRST
    next_step = (Path(result["output_dir"]) / "next_step_decision.md").read_text(encoding="utf-8")
    assert decision.COMMIT_FIRST in next_step

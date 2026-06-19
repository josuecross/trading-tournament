from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

import run_parallel_research_discovery as discovery


def synthetic_raw(symbol: str, periods: int = 620, drift: float = 0.00025) -> pd.DataFrame:
    dates = pd.bdate_range("2021-01-01", periods=periods)
    prices = [50.0 + len(symbol)]
    for idx in range(1, periods):
        prices.append(prices[-1] * (1 + drift + 0.001 * ((idx % 7) - 3) / 10.0))
    return pd.DataFrame(
        {
            "Date": dates,
            "Open": prices,
            "High": [price * 1.01 for price in prices],
            "Low": [price * 0.99 for price in prices],
            "Close": prices,
            "Adj Close": prices,
            "Volume": [100000] * periods,
            "Dividends": [0.0] * periods,
            "Stock Splits": [0.0] * periods,
        }
    )


def write_cache(root: Path, symbol: str, drift: float = 0.00025) -> None:
    normalized = discovery.build_adjusted_ohlc(synthetic_raw(symbol, drift=drift), symbol)
    target = root / "data" / "cache" / f"{symbol}.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    normalized.to_csv(target, index=False)


def write_registry(root: Path) -> None:
    rows = []
    for row_id, active in [
        ("current_no_cash_proxy_alpha_AB", True),
        ("paper_forward_vm_quality_lowvol_proxy_v1", True),
        ("paper_forward_dsr_sector_equal_weight_defensive_filter_v1", True),
        ("SPY_200d_trend_model", True),
        ("gtaa_faber_style_benchmark_lane", False),
    ]:
        rows.append(
            {
                "id": row_id,
                "display_name": row_id,
                "credibility_tier": "tier4_paper_forward" if active else "tier1_research_queue",
                "status": "active_observation" if active else "research_queue",
                "current_status": "active_observation" if active else "research_queue",
                "paper_forward_active": active,
                "allowed_next_action": "observe_only" if active else "research_sample_review",
                "next_allowed_action": "observe_only" if active else "research_sample_review",
                "allowed_next_actions": ["observe_only" if active else "research_sample_review"],
                "implementation_status": "implemented" if active else "not_implemented",
                "real_money_recommendation": False,
                "candidate_exhaustive_run": False,
            }
        )
    path = root / "strategy_lab" / "strategy_registry.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {"registry": {"schema_version": 1, "project": "trading_tournament", "research_only": True}, "strategies": rows},
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def write_queue(root: Path) -> None:
    queue = {
        "approved_symbols": ["SPY", "QQQ", "EFA", "EEM", "GLD", "IEF", "BIL"],
        "families": [
            {
                "family_id": "gtaa_faber_style_benchmark_lane",
                "priority_rank": 1,
                "run_enabled": True,
                "stage": "research_sample",
                "evidence_tier": "exploratory",
                "approved_symbols": ["SPY", "QQQ", "EFA", "EEM", "GLD", "IEF", "BIL"],
                "max_variants": 1,
                "variants": [
                    {
                        "strategy_id": "gtaa_equal_weight_trend_filter_v1",
                        "rule_type": "gtaa_equal_weight_trend_filter",
                        "universe": ["SPY", "QQQ", "EFA", "EEM", "GLD", "IEF", "BIL"],
                    }
                ],
            }
        ],
    }
    path = root / discovery.QUEUE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(queue, sort_keys=False), encoding="utf-8")


def seed(root: Path) -> None:
    for offset, symbol in enumerate(["SPY", "QQQ", "EFA", "EEM", "GLD", "IEF", "BIL"]):
        write_cache(root, symbol, drift=0.00018 + offset * 0.00001)


def test_combined_benchmark_delta_export_and_protected_rows(tmp_path: Path) -> None:
    write_registry(tmp_path)
    write_queue(tmp_path)
    seed(tmp_path)
    registry_before = yaml.safe_load((tmp_path / discovery.REGISTRY_PATH).read_text(encoding="utf-8"))
    protected_before = discovery.protected_snapshot(registry_before)

    result = discovery.run_parallel_discovery(tmp_path, allow_download=False)

    latest = Path(result["output_dir"])
    delta_path = latest / "combined_benchmark_delta.csv"
    assert delta_path.exists()
    delta = pd.read_csv(delta_path)
    assert set(discovery.COMBINED_BENCHMARK_IDS) <= set(delta["benchmark_id"])

    active_combo = delta[delta["benchmark_id"] == "active_combo"].iloc[0]
    assert active_combo["comparison_status"] == "unavailable"
    assert active_combo["benchmark_available"] in {False, "False", "false"}
    assert pd.isna(active_combo["delta_median_equity"]) or str(active_combo["delta_median_equity"]).strip() not in {"0", "0.0"}
    assert isinstance(active_combo["missing_reason"], str) and active_combo["missing_reason"]

    available = delta[delta["comparison_status"] == "available"].iloc[0]
    expected_delta = float(available["strategy_median_equity"]) - float(available["benchmark_median_equity"])
    assert abs(float(available["delta_median_equity"]) - expected_delta) < 1e-9
    assert available["delta_sign_check"] == "passed"

    registry_after = yaml.safe_load((tmp_path / discovery.REGISTRY_PATH).read_text(encoding="utf-8"))
    assert discovery.protected_snapshot(registry_after) == protected_before

    manifest = yaml.safe_load((latest / "parallel_research_discovery_manifest.json").read_text(encoding="utf-8"))
    assert manifest["provider_api_called"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["paper_forward_activation"] is False
    assert manifest["real_money_recommendation"] is False

    label_check = yaml.safe_load(
        (tmp_path / discovery.LABEL_UPDATE_DIR / "exploratory_gate_label_consistency_check.json").read_text(encoding="utf-8")
    )
    assert label_check["active_observations_unchanged"] is True
    assert label_check["no_real_money_recommendation"] is True

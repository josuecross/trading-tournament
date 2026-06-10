from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import platform
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any, Callable
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.data import DataQualityError, _standardize_raw_columns, build_adjusted_ohlc


SUBJECT_ID = "paper_forward_observation_cache_update"
STRATEGY_ID = "combo_SPY200d_GLD_50_50_v1"
REGISTRY_ID = "profit_combo_SPY200d_GLD_50_50_v1"
CONTROL_ID = "SPY_200d_trend_model"
APPROVED_SYMBOLS = ("SPY", "GLD", "BIL")
CANONICAL_RULE_HASH = "6695f0d3ec403e2f377d99f3f63d1fc57a66f45f2c27a9072ab8c0a60a19ee67"
CONFIG_PATH = Path(__file__).resolve().with_name("cache_update_config.yaml")
EVIDENCE_ROOT = REPO_ROOT / "evidence" / "data_acquisition_runs" / SUBJECT_ID
LATEST_DIR = EVIDENCE_ROOT / "latest"
LATEST_ZIP = EVIDENCE_ROOT / "latest_cache_update_packet.zip"
OBS_DIR = REPO_ROOT / "paper_forward_observations" / STRATEGY_ID
OBS_LATEST_DIR = REPO_ROOT / "evidence" / "paper_forward_observations" / STRATEGY_ID / "latest"
OBS_ZIP = REPO_ROOT / "evidence" / "paper_forward_observations" / STRATEGY_ID / "latest_observation_activation_packet.zip"

Downloader = Callable[[str, dict[str, Any]], pd.DataFrame]


@dataclass
class CacheUpdateOutputs:
    run_id: str
    run_dir: Path
    latest_dir: Path
    zip_path: Path
    coverage: pd.DataFrame
    quality: pd.DataFrame
    cache_manifest: pd.DataFrame
    manifest: dict[str, Any]


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def validate_requested_symbols(config: dict[str, Any], requested_symbols: list[str] | None = None) -> list[str]:
    allowed = [str(symbol).upper() for symbol in config.get("allowed_symbols", [])]
    symbols = [str(symbol).upper() for symbol in (requested_symbols if requested_symbols is not None else allowed)]
    if allowed != list(APPROVED_SYMBOLS):
        raise ValueError(f"cache update allowed_symbols must be exactly {', '.join(APPROVED_SYMBOLS)}")
    if sorted(symbols) != sorted(allowed):
        raise ValueError(f"requested symbols must exactly match approved symbols: {', '.join(allowed)}")
    unapproved = sorted(set(symbols) - set(allowed))
    if unapproved:
        raise ValueError(f"unapproved cache update symbols requested: {', '.join(unapproved)}")
    return symbols


def package_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for package in ["pandas", "numpy", "yfinance", "PyYAML"]:
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = "not_installed"
    return versions


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def default_yfinance_downloader(symbol: str, request_settings: dict[str, Any]) -> pd.DataFrame:
    import yfinance as yf

    kwargs: dict[str, Any] = {
        "start": request_settings.get("start", "2007-01-01"),
        "end": request_settings.get("end"),
        "auto_adjust": bool(request_settings.get("auto_adjust", False)),
        "actions": bool(request_settings.get("actions", True)),
        "progress": bool(request_settings.get("progress", False)),
    }
    if kwargs["end"] is None:
        kwargs.pop("end")
    signature = inspect.signature(yf.download)
    if "multi_level_index" in signature.parameters:
        kwargs["multi_level_index"] = bool(request_settings.get("multi_level_index", False))
    if "timeout" in signature.parameters and request_settings.get("timeout") is not None:
        kwargs["timeout"] = float(request_settings.get("timeout", 20))
    try:
        return yf.download(symbol, **kwargs)
    except TypeError as exc:
        if "multi_level_index" not in str(exc):
            raise
        kwargs.pop("multi_level_index", None)
        return yf.download(symbol, **kwargs)


def normalized_date_series(frame: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)


def read_existing_cache(cache_path: Path) -> pd.DataFrame:
    if not cache_path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(cache_path)
    if "date" not in frame.columns:
        return pd.DataFrame()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    return frame.dropna(subset=["date"])


def merge_existing_and_downloaded(existing: pd.DataFrame, downloaded: pd.DataFrame) -> pd.DataFrame:
    frames = [frame for frame in [existing, downloaded] if frame is not None and not frame.empty]
    if not frames:
        return pd.DataFrame()
    merged = pd.concat(frames, ignore_index=True, sort=False)
    merged["date"] = pd.to_datetime(merged["date"], errors="coerce").dt.tz_localize(None)
    merged = merged.dropna(subset=["date"]).sort_values("date").drop_duplicates("date", keep="last")
    for column in downloaded.columns:
        if column not in merged.columns:
            merged[column] = pd.NA
    return merged[list(downloaded.columns)]


def analyze_symbol(
    symbol: str,
    raw: pd.DataFrame | None,
    normalized_download: pd.DataFrame | None,
    merged_cache: pd.DataFrame | None,
    cache_path: Path,
    requested_activation_date: str,
    error: str = "",
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    downloaded_or_refreshed = raw is not None and not raw.empty
    cache_written = cache_path.exists() and merged_cache is not None and not merged_cache.empty
    duplicate_date_count = 0
    missing_adj = missing_close = missing_volume = 0
    adjusted_close_available = raw_close_available = dividends_available = splits_available = False
    adjusted_constructible = normalized_download is not None and not normalized_download.empty and not error

    if raw is not None and not raw.empty:
        try:
            raw_standard = _standardize_raw_columns(raw, symbol)
            raw_dates = normalized_date_series(raw_standard)
            duplicate_date_count = int(raw_dates.duplicated().sum())
            missing_adj = int(raw_standard["raw_adj_close"].isna().sum())
            missing_close = int(raw_standard["raw_close"].isna().sum())
            missing_volume = int(raw_standard["raw_volume"].isna().sum())
            adjusted_close_available = "raw_adj_close" in raw_standard and missing_adj < len(raw_standard)
            raw_close_available = "raw_close" in raw_standard and missing_close < len(raw_standard)
            dividends_available = "dividends" in raw_standard
            splits_available = "stock_splits" in raw_standard
        except Exception:
            pass

    row_count = int(len(merged_cache)) if merged_cache is not None else 0
    first_date = str(normalized_date_series(merged_cache).min().date()) if merged_cache is not None and not merged_cache.empty else ""
    last_date = str(normalized_date_series(merged_cache).max().date()) if merged_cache is not None and not merged_cache.empty else ""
    supports_date = bool(last_date and pd.Timestamp(last_date) >= pd.Timestamp(requested_activation_date))
    if error or not downloaded_or_refreshed or not cache_written or not adjusted_constructible or missing_adj or missing_close or duplicate_date_count:
        quality_status = "fail"
    elif not supports_date:
        quality_status = "warning"
    elif missing_volume:
        quality_status = "warning"
    else:
        quality_status = "pass"
    if error:
        notes = error
    elif not supports_date:
        notes = f"cache updated but latest date {last_date or 'unavailable'} does not support requested activation date {requested_activation_date}"
    elif missing_volume:
        notes = "warning: missing volume values"
    else:
        notes = "pass"

    coverage = {
        "symbol": symbol,
        "downloaded_or_refreshed": downloaded_or_refreshed,
        "cache_written": cache_written,
        "row_count": row_count,
        "first_date": first_date,
        "last_date": last_date,
        "supports_requested_activation_date": supports_date,
        "coverage_notes": notes,
    }
    quality = {
        "symbol": symbol,
        "downloaded_or_refreshed": downloaded_or_refreshed,
        "cache_written": cache_written,
        "row_count": row_count,
        "first_date": first_date,
        "last_date": last_date,
        "duplicate_date_count": duplicate_date_count,
        "missing_adjusted_close_count": missing_adj,
        "missing_close_count": missing_close,
        "missing_volume_count": missing_volume,
        "adjusted_close_available": adjusted_close_available,
        "raw_close_available": raw_close_available,
        "dividends_available": dividends_available,
        "splits_available": splits_available,
        "adjusted_ohlc_constructible": adjusted_constructible,
        "supports_requested_activation_date": supports_date,
        "quality_status": quality_status,
        "quality_notes": notes,
    }
    cache = {
        "symbol": symbol,
        "cache_path": str(cache_path.relative_to(REPO_ROOT) if cache_path.is_relative_to(REPO_ROOT) else cache_path),
        "rows_written": row_count if cache_written else 0,
        "sha256": sha256_file(cache_path) if cache_written else "",
        "write_status": "written_merged_refresh" if cache_written else "failed",
    }
    return coverage, quality, cache


def latest_common_date(coverage: pd.DataFrame) -> str:
    if coverage.empty or not coverage["last_date"].astype(str).ne("").all():
        return ""
    return str(pd.to_datetime(coverage["last_date"]).min().date())


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def write_report_files(
    run_dir: Path,
    run_id: str,
    config: dict[str, Any],
    metadata: dict[str, Any],
    coverage: pd.DataFrame,
    quality: pd.DataFrame,
    cache_manifest: pd.DataFrame,
    manifest: dict[str, Any],
) -> None:
    failed = quality[quality["quality_status"].astype(str).eq("fail")]["symbol"].astype(str).tolist() if not quality.empty else []
    refreshed = coverage[coverage["downloaded_or_refreshed"].astype(bool)]["symbol"].astype(str).tolist() if not coverage.empty else []
    readme = f"""# Paper-Forward Cache Update Packet

This is a controlled cache update only for `{config.get('subject_id')}`.

Allowed symbols are `SPY`, `GLD`, and `BIL` only.

No strategy rule was changed. No backtest was run. No Profit Exploration run was executed. No broker integration, live orders, order placement, or real-money recommendation were added.

Raw OHLCV/cache rows are excluded from this compact evidence packet and from advisor upload packets.
"""
    summary = f"""# Cache Update Summary

Run id: `{run_id}`

Requested activation date: `{manifest['requested_activation_date']}`

Provider used: `{config.get('provider')}`

Symbols updated/refreshed: {', '.join(refreshed) or 'none'}

Symbols failed: {', '.join(failed) or 'none'}

Latest common cached date across SPY/GLD/BIL: `{manifest['latest_common_cached_date'] or 'unavailable'}`

Activation date supported: `{str(manifest['requested_activation_date_supported']).lower()}`

Combo activation may proceed: `{str(manifest['requested_activation_date_supported'] and not failed).lower()}`

No real-money recommendation.
"""
    warnings = """# Warnings And Limitations

- yfinance/Yahoo data can have revisions, gaps, personal-use/licensing limits, ticker mapping issues, and adjustment differences.
- This cache update does not validate strategy performance.
- Raw OHLCV/cache rows are excluded from compact evidence and advisor upload packets.
- This packet does not change rules, run a backtest, run Profit Exploration, connect to brokers, place orders, or recommend real-money trading.
"""
    (run_dir / "README_FOR_ADVISOR.md").write_text(readme, encoding="utf-8")
    (run_dir / "cache_update_summary.md").write_text(summary, encoding="utf-8")
    write_json(run_dir / "cache_update_metadata.json", metadata)
    coverage.to_csv(run_dir / "symbol_coverage_summary.csv", index=False)
    quality.to_csv(run_dir / "data_quality_summary.csv", index=False)
    cache_manifest.to_csv(run_dir / "cache_write_manifest.csv", index=False)
    (run_dir / "warnings_and_limitations.md").write_text(warnings, encoding="utf-8")
    write_json(run_dir / "cache_update_manifest.json", manifest)


def sync_latest_and_zip(run_dir: Path, latest_dir: Path, zip_path: Path) -> None:
    latest_dir.mkdir(parents=True, exist_ok=True)
    for existing in latest_dir.iterdir():
        if existing.is_file():
            existing.unlink()
    for path in sorted(run_dir.iterdir()):
        if path.is_file():
            shutil.copy2(path, latest_dir / path.name)
    if zip_path.exists():
        zip_path.unlink()
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(latest_dir.iterdir()):
            if path.is_file():
                archive.write(path, path.name)


def update_observation_activation(repo_root: Path, manifest: dict[str, Any]) -> None:
    supported = bool(manifest["requested_activation_date_supported"])
    status = "active_paper_demo_observation" if supported else "active_waiting_for_next_cached_trading_day"
    activation_date = manifest["requested_activation_date"] if supported else None
    blocker = "" if supported else "cached_data_not_available_through_requested_activation_date"
    config_path = OBS_DIR / "observation_config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    config.update(
        {
            "status": status,
            "paper_forward_activation_date": activation_date,
            "latest_common_cached_date": manifest["latest_common_cached_date"] or None,
            "data_available_through_requested_date": supported,
            "canonical_rule_hash": CANONICAL_RULE_HASH,
            "hash_source_type": "source_spec_reconstructed_hash",
            "rule_hash_verified": True,
            "activation_blocker": blocker,
            "activation_note": (
                "The canonical rule hash is verified and local cache supports the requested activation date. "
                "Combo may run as a separate simulated paper/demo observation track; SPY_200d remains the frozen control."
                if supported
                else "The canonical rule hash is verified, but local cache still does not support the requested activation date. "
                "No active combo metrics may be fabricated."
            ),
        }
    )
    config_path.write_text(yaml.safe_dump(config, sort_keys=False, allow_unicode=False), encoding="utf-8")

    activation_manifest_path = OBS_DIR / "observation_activation_manifest.json"
    activation_manifest = json.loads(activation_manifest_path.read_text(encoding="utf-8")) if activation_manifest_path.exists() else {}
    activation_manifest.update(
        {
            "requested_activation_date": manifest["requested_activation_date"],
            "paper_forward_activation_date": activation_date,
            "latest_common_cached_date": manifest["latest_common_cached_date"] or None,
            "activation_status": status,
            "canonical_rule_hash": CANONICAL_RULE_HASH,
            "hash_source_type": "source_spec_reconstructed_hash",
            "rule_hash_verified": True,
            "activation_blocker": blocker,
            "paper_forward_active": supported,
            "spy200d_replaced": False,
            "strategy_rules_changed": False,
            "backtest_run": False,
            "profit_exploration_run": False,
            "data_downloaded": bool(manifest["data_downloaded_or_refreshed"]),
            "broker_integration": False,
            "live_orders": False,
            "order_placement": False,
            "real_money_recommendation": False,
            "latest_folder_file_count": 6,
        }
    )
    write_json(activation_manifest_path, activation_manifest)

    record_path = OBS_DIR / "ACTIVATION_RECORD.md"
    record_path.write_text(
        f"""# Activation Record

activation_status: `{status}`

requested_activation_date: `{manifest['requested_activation_date']}`

paper_forward_activation_date: `{activation_date or 'not_active'}`

latest_common_cached_date: `{manifest['latest_common_cached_date'] or 'unavailable'}`

canonical_rule_hash: `{CANONICAL_RULE_HASH}`

rule_hash_verified: `true`

SPY_200d_replaced: `false`

## Cache Update Result

Controlled cache update run `{manifest['run_id']}` refreshed only `SPY`, `GLD`, and `BIL`.

Activation date supported: `{str(supported).lower()}`

## Boundary

No strategy rules were changed. No backtest was run. No Profit Exploration run was run. No broker integration, live orders, order placement, or real-money recommendation was added.
""",
        encoding="utf-8",
    )
    rule_hash_record = OBS_DIR / "RULE_HASH_RECORD.md"
    existing = rule_hash_record.read_text(encoding="utf-8") if rule_hash_record.exists() else "# Rule Hash Record\n"
    note = (
        "\n\n## Cache Freshness Update\n\n"
        f"Controlled SPY/GLD/BIL cache update run `{manifest['run_id']}` recorded latest common cached date "
        f"`{manifest['latest_common_cached_date'] or 'unavailable'}` and activation-date support "
        f"`{str(supported).lower()}`. The canonical rule hash remains `{CANONICAL_RULE_HASH}`.\n"
    )
    if "## Cache Freshness Update" not in existing:
        rule_hash_record.write_text(existing.rstrip() + note, encoding="utf-8")

    sync_latest_and_zip(OBS_DIR, OBS_LATEST_DIR, OBS_ZIP)


def update_registry(repo_root: Path, manifest: dict[str, Any]) -> None:
    supported = bool(manifest["requested_activation_date_supported"])
    registry_path = repo_root / "strategy_lab" / "strategy_registry.yaml"
    data = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    for row in data.get("strategies", []):
        if row.get("id") == REGISTRY_ID:
            row["status"] = "active_paper_demo_observation" if supported else "active_waiting_for_next_cached_trading_day"
            row["paper_forward_active"] = supported
            row["implementation_status"] = "implemented_research_candidate"
            row["paper_forward_allowed_by_risk_framework"] = supported
            row["real_money_recommendation"] = False
            row["broker_integration"] = False
            row["live_orders"] = False
            row["observation_id"] = "combo_SPY200d_GLD_50_50_v1_observation_v1"
            row["canonical_rule_hash"] = CANONICAL_RULE_HASH
            row["hash_source_type"] = "source_spec_reconstructed_hash"
            row["evidence_source"] = "paper_forward_cache_update_and_observation_activation"
            row["latest_evidence_path"] = "evidence/paper_forward_observations/combo_SPY200d_GLD_50_50_v1/latest/"
            row["latest_known_result_summary"] = (
                f"Controlled SPY/GLD/BIL cache update run {manifest['run_id']} recorded latest common cached date "
                f"{manifest['latest_common_cached_date'] or 'unavailable'} for requested activation date "
                f"{manifest['requested_activation_date']}. "
                + (
                    "Combo is active as a separate simulated paper/demo observation track. SPY_200d remains frozen control and is not replaced."
                    if supported
                    else "Combo remains waiting because the requested activation date is not supported by cache. SPY_200d remains frozen control and is not replaced."
                )
            )
            row["allowed_next_action"] = "run_monthly_paper_forward_checkpoint" if supported else "controlled_cache_update_or_next_cached_observation_date"
            forbidden = list(row.get("forbidden_next_actions", []))
            for action in [
                "replace_spy200d_without_governance",
                "promote_to_real_money",
                "add_broker_integration",
                "place_live_orders",
                "change_strategy_rules",
                "tune_parameters",
                "skip_checkpoints",
                "fabricate_missing_data",
            ]:
                if action not in forbidden:
                    forbidden.append(action)
            row["forbidden_next_actions"] = forbidden
            row["promotion_blockers"] = (
                "paper_demo_observation_only;no_real_money_promotion"
                if supported
                else "waiting_for_cached_data_after_hash_resolution;not_paper_forward_active;no_real_money_promotion"
            )
            row["promotion_requirements"] = (
                "Run monthly paper/demo checkpoints under frozen rules; keep SPY_200d as frozen control; no real-money promotion without separate governance."
                if supported
                else "Wait for cached SPY/GLD/BIL data through the activation date or run a separately approved controlled cache update."
            )
            row["notes"] = (
                "Controlled cache update resolved the data-date blocker; combo is paper/demo only and does not replace SPY_200d."
                if supported
                else "Controlled cache update did not resolve the data-date blocker; combo remains inactive and no metrics are fabricated."
            )
        elif row.get("id") == CONTROL_ID:
            row["paper_forward_active"] = True
            row["rules_frozen"] = True
            row.pop("replaced_by_combo", None)
    registry_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=False), encoding="utf-8")


def run_cache_update(
    repo_root: Path = REPO_ROOT,
    config_path: Path = CONFIG_PATH,
    downloader: Downloader | None = None,
    run_id: str | None = None,
    update_governance: bool = True,
) -> CacheUpdateOutputs:
    config = load_config(config_path)
    symbols = validate_requested_symbols(config)
    requested_activation_date = str(config["requested_activation_date"])
    request_settings = dict(config.get("request_settings", {}))
    cache_root = repo_root / str(config.get("cache", {}).get("target_root", "data/cache"))
    cache_root.mkdir(parents=True, exist_ok=True)
    run_id = run_id or utc_run_id()
    run_dir = EVIDENCE_ROOT / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    downloader = downloader or default_yfinance_downloader

    coverage_rows: list[dict[str, Any]] = []
    quality_rows: list[dict[str, Any]] = []
    cache_rows: list[dict[str, Any]] = []
    for symbol in symbols:
        raw: pd.DataFrame | None = None
        normalized_download: pd.DataFrame | None = None
        merged_cache: pd.DataFrame | None = None
        error = ""
        cache_path = cache_root / f"{symbol}.csv"
        try:
            raw = downloader(symbol, request_settings)
            if raw is None or raw.empty:
                raise DataQualityError(f"{symbol}: provider returned no rows")
            normalized_download = build_adjusted_ohlc(raw, symbol)
            existing = read_existing_cache(cache_path)
            merged_cache = merge_existing_and_downloaded(existing, normalized_download)
            if merged_cache.empty:
                raise DataQualityError(f"{symbol}: merged cache is empty")
            merged_cache.to_csv(cache_path, index=False)
        except Exception as exc:
            error = str(exc)
            existing = read_existing_cache(cache_path)
            if not existing.empty:
                merged_cache = existing
        coverage, quality, cache = analyze_symbol(
            symbol,
            raw,
            normalized_download,
            merged_cache,
            cache_path,
            requested_activation_date,
            error,
        )
        coverage_rows.append(coverage)
        quality_rows.append(quality)
        cache_rows.append(cache)

    coverage_df = pd.DataFrame(coverage_rows)
    quality_df = pd.DataFrame(quality_rows)
    cache_df = pd.DataFrame(cache_rows)
    common_date = latest_common_date(coverage_df)
    supported = bool(common_date and pd.Timestamp(common_date) >= pd.Timestamp(requested_activation_date))
    failed = quality_df["quality_status"].astype(str).eq("fail").any()
    supported = supported and not bool(failed)
    timestamp = utc_timestamp()
    versions = package_versions()
    metadata = {
        "run_id": run_id,
        "timestamp": timestamp,
        "provider": config.get("provider"),
        "provider_id": "yfinance_compatible",
        "request_settings": request_settings,
        "package_versions": versions,
        "yfinance_version": versions.get("yfinance", "not_installed"),
        "python_version": platform.python_version(),
        "symbols": symbols,
        "cache_target_root": str(cache_root.relative_to(repo_root) if cache_root.is_relative_to(repo_root) else cache_root),
        "canonical_combo_rule_hash": str(config.get("canonical_rule_hash")),
        "requested_activation_date": requested_activation_date,
        "broker_integration": False,
        "live_orders": False,
        "order_placement": False,
        "real_money_recommendation": False,
    }
    manifest = {
        "run_id": run_id,
        "timestamp": timestamp,
        "data_downloaded_or_refreshed": bool(coverage_df["downloaded_or_refreshed"].any()),
        "yfinance_compatible_provider_call": True,
        "keyed_provider_used": False,
        "api_key_or_secret_written": False,
        "raw_ohlcv_included": False,
        "strategy_implemented": False,
        "backtest_run": False,
        "profit_exploration_run": False,
        "paper_forward_rule_changed": False,
        "broker_integration": False,
        "live_orders": False,
        "order_placement": False,
        "real_money_recommendation": False,
        "requested_activation_date": requested_activation_date,
        "latest_common_cached_date": common_date,
        "requested_activation_date_supported": supported,
        "latest_folder_file_count": 8,
        "quality_counts": {status: int(quality_df["quality_status"].eq(status).sum()) for status in ["pass", "warning", "fail"]},
    }
    write_report_files(run_dir, run_id, config, metadata, coverage_df, quality_df, cache_df, manifest)
    sync_latest_and_zip(run_dir, LATEST_DIR, LATEST_ZIP)
    if update_governance:
        update_observation_activation(repo_root, manifest)
        update_registry(repo_root, manifest)
    return CacheUpdateOutputs(run_id, run_dir, LATEST_DIR, LATEST_ZIP, coverage_df, quality_df, cache_df, manifest)


def main() -> int:
    parser = argparse.ArgumentParser(description="Controlled SPY/GLD/BIL cache update for combo paper-forward observation.")
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    args = parser.parse_args()
    outputs = run_cache_update(config_path=args.config)
    refreshed = outputs.coverage[outputs.coverage["downloaded_or_refreshed"].astype(bool)]["symbol"].astype(str).tolist()
    failed = outputs.quality[outputs.quality["quality_status"].astype(str).eq("fail")]["symbol"].astype(str).tolist()
    print(f"run_id={outputs.run_id}")
    print(f"refreshed_symbols={','.join(refreshed)}")
    print(f"failed_symbols={','.join(failed)}")
    print(f"latest_common_cached_date={outputs.manifest['latest_common_cached_date']}")
    print(f"requested_activation_date={outputs.manifest['requested_activation_date']}")
    print(f"requested_activation_date_supported={str(outputs.manifest['requested_activation_date_supported']).lower()}")
    print(f"latest_dir={outputs.latest_dir}")
    print(f"latest_file_count={outputs.manifest['latest_folder_file_count']}")
    print(f"zip_path={outputs.zip_path}")
    print("strategy_implemented=false")
    print("backtest_run=false")
    print("profit_exploration_run=false")
    print("broker_integration=false")
    print("live_orders=false")
    print("real_money_recommendation=false")
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())

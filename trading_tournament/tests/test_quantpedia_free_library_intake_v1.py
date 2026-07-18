from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from strategy_lab.research_os.research import quantpedia_free_library_intake_v1 as intake


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "quantpedia_free_library_intake_v1" / "latest"
INPUT_DIR = ROOT / intake.INPUT_DIR
LIBRARY_DIR = ROOT / intake.LIBRARY_DIR
REGISTRY = ROOT / intake.REGISTRY_PATH
ACTIVE_OBSERVATIONS = ROOT / intake.ACTIVE_OBSERVATIONS_PATH


@pytest.fixture(scope="module", autouse=True)
def generated_intake() -> dict[str, object]:
    return intake.run(ROOT)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_blocker() -> dict[str, object]:
    return json.loads((EVIDENCE / "input_blocker.json").read_text(encoding="utf-8"))


def test_no_usable_capture_creates_only_input_blocker() -> None:
    assert not INPUT_DIR.exists()
    files = sorted(path.name for path in EVIDENCE.iterdir() if path.is_file())
    assert files == ["input_blocker.json"]
    payload = read_blocker()
    assert payload["outcome"] == "authorized_quantpedia_capture_required"
    assert payload["next_action"] == "authorized_quantpedia_capture_required"
    assert payload["usable_input_file_count"] == 0


def test_supported_capture_formats_are_reported() -> None:
    payload = read_blocker()
    assert payload["supported_input_formats"] == [
        "CSV",
        "JSON",
        "Browser-saved HTML",
        "Plain-text title-and-URL list",
    ]
    assert payload["supported_extensions"] == [".csv", ".json", ".html", ".htm", ".txt"]


def test_expected_count_reconciled_without_fabrication() -> None:
    payload = read_blocker()
    assert payload["expected_free_strategy_count"] == 82
    assert payload["raw_input_records"] == 0
    assert payload["normalized_strategy_count"] == 0
    assert payload["difference_from_expected_count"] == 82
    assert payload["missing_strategies_fabricated"] is False
    assert payload["empty_library_created"] is False
    assert not LIBRARY_DIR.exists()


def test_no_network_login_credentials_or_private_access() -> None:
    guardrails = read_blocker()["access_guardrails"]
    for key in [
        "network_used",
        "quantpedia_scraped",
        "login_requested",
        "credentials_requested",
        "cookies_accessed",
        "session_tokens_accessed",
        "private_endpoints_used",
        "provider_data_downloaded",
    ]:
        assert guardrails[key] is False


def test_no_content_boundary_or_code_copying_violation() -> None:
    boundary = read_blocker()["content_boundary"]
    assert boundary["full_quantpedia_articles_stored"] is False
    assert boundary["charts_or_performance_tables_stored"] is False
    assert boundary["quantpedia_or_quantconnect_code_copied"] is False


def test_no_strategy_verification_backtest_promotion_or_broker_path() -> None:
    guardrails = read_blocker()["access_guardrails"]
    for key in [
        "original_papers_verified",
        "strategy_backtest_run",
        "performance_ranking_created",
        "paper_demo_activation",
        "broker_or_live_path",
        "real_money_recommendation",
    ]:
        assert guardrails[key] is False


def test_registry_and_active_observations_remain_unchanged() -> None:
    payload = read_blocker()
    assert payload["strategy_registry_hash_before"] == sha256(REGISTRY)
    assert payload["strategy_registry_hash_after"] == sha256(REGISTRY)
    assert payload["active_observations_hash_before"] == sha256(ACTIVE_OBSERVATIONS)
    assert payload["active_observations_hash_after"] == sha256(ACTIVE_OBSERVATIONS)


def test_output_generation_is_deterministic() -> None:
    before = sha256(EVIDENCE / "input_blocker.json")
    intake.run(ROOT)
    after = sha256(EVIDENCE / "input_blocker.json")
    assert before == after

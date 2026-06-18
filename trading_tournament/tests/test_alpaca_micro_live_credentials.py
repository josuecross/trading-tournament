from __future__ import annotations

from pathlib import Path

import pytest

from execution_lab.alpaca_micro_live_v1.adapters.credentials import load_alpaca_credentials, mask_secret
from execution_lab.alpaca_micro_live_v1.execution import check_credentials

pytestmark = pytest.mark.alpaca_micro_live


def test_env_local_credentials_load_without_printing_secrets(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    env_path = tmp_path / ".env.local"
    env_path.write_text(
        "ALPACA_PAPER_API_KEY=PK123456789SECRET\n"
        "ALPACA_PAPER_SECRET_KEY=SK123456789SECRET\n",
        encoding="utf-8",
    )
    credentials = load_alpaca_credentials("paper", [env_path])
    assert credentials.present is True
    assert credentials.masked_api_key == "PK12...CRET"
    assert credentials.masked_secret_key == "SK12...CRET"

    assert check_credentials.main(["--environment", "paper", "--no-network"]) == 0
    output = capsys.readouterr().out
    assert "PK123456789SECRET" not in output
    assert "SK123456789SECRET" not in output


def test_mask_secret_masks_short_and_long_values() -> None:
    assert mask_secret(None) == "missing"
    assert mask_secret("short") == "*****"
    assert mask_secret("ABCD1234WXYZ") == "ABCD...WXYZ"

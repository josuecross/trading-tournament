from __future__ import annotations

import pytest

from trading_tournament.execution_lab.alpaca_micro_live_v1.adapters.credentials import (
    load_alpaca_credentials,
    mask_secret,
)


pytestmark = pytest.mark.alpaca_micro_live


def test_credentials_load_from_env_local_without_printing_secrets(tmp_path, monkeypatch):
    monkeypatch.delenv("ALPACA_PAPER_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_PAPER_SECRET_KEY", raising=False)
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        """
# comment
ALPACA_PAPER_API_KEY="PK123456789"
ALPACA_PAPER_SECRET_KEY='SK987654321'
ALPACA_LIVE_API_KEY=LK_DISABLED
""",
        encoding="utf-8",
    )
    creds = load_alpaca_credentials("paper", [env_file])
    assert creds.present
    assert creds.live_credentials_detected
    assert creds.masked_api_key == "PK12...6789"
    assert creds.masked_secret_key == "SK98...4321"
    assert "PK123456789" not in creds.masked_api_key
    assert "SK987654321" not in creds.masked_secret_key


def test_environment_variables_take_priority(tmp_path, monkeypatch):
    env_file = tmp_path / ".env.local"
    env_file.write_text("ALPACA_PAPER_API_KEY=filekey\nALPACA_PAPER_SECRET_KEY=filesecret\n", encoding="utf-8")
    monkeypatch.setenv("ALPACA_PAPER_API_KEY", "envkey1234")
    monkeypatch.setenv("ALPACA_PAPER_SECRET_KEY", "envsecret1234")
    creds = load_alpaca_credentials("paper", [env_file])
    assert creds.api_key == "envkey1234"
    assert creds.secret_key == "envsecret1234"
    assert mask_secret("abc") == "***"

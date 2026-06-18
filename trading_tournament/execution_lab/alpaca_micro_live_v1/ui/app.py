from __future__ import annotations

from pathlib import Path

import streamlit as st

from execution_lab.alpaca_micro_live_v1 import MODULE_ROOT
from execution_lab.alpaca_micro_live_v1.adapters.alpaca_client import AlpacaClient, AlpacaClientConfig
from execution_lab.alpaca_micro_live_v1.adapters.credentials import load_alpaca_credentials
from execution_lab.alpaca_micro_live_v1.ui.actions import (
    DEFAULT_CONFIG,
    DEFAULT_RISK,
    credential_summary,
    generate_ui_signal,
    start_runtime_session,
)
from execution_lab.alpaca_micro_live_v1.ui.components import status_label
from execution_lab.alpaca_micro_live_v1.ui.log_viewer import read_tail


st.set_page_config(page_title="Alpaca Micro Runtime", layout="wide")
st.title("Alpaca Micro Runtime")

tabs = st.tabs(["Credentials", "Market Clock", "Strategy Signal", "Runtime Runner"])

with tabs[0]:
    summary = credential_summary()
    st.write({"paper_credentials": status_label(bool(summary["present"])), "source": summary["source"]})
    st.write({"api_key": summary["api_key"], "secret_key": summary["secret_key"]})
    st.write({"live_credentials_detected_but_disabled": summary["live_detected_disabled"]})
    if st.button("Test Paper Connection"):
        creds = load_alpaca_credentials("paper")
        try:
            account = AlpacaClient(creds, AlpacaClientConfig()).get_account()
            st.success(f"Paper connection ok: {account.get('status', 'unknown')}")
        except Exception as exc:
            st.error(f"Paper connection failed: {type(exc).__name__}")

with tabs[1]:
    if st.button("Refresh Market Clock"):
        creds = load_alpaca_credentials("paper")
        try:
            clock = AlpacaClient(creds, AlpacaClientConfig()).get_market_clock()
            st.json({"is_open": clock.get("is_open"), "next_open": clock.get("next_open"), "next_close": clock.get("next_close")})
        except Exception as exc:
            st.error(f"Clock check failed: {type(exc).__name__}")

with tabs[2]:
    config_path = Path(st.text_input("Config", str(DEFAULT_CONFIG), key="signal_config"))
    risk_path = Path(st.text_input("Risk limits", str(DEFAULT_RISK), key="signal_risk"))
    if st.button("Generate Alpaca Runtime Signal"):
        try:
            output = generate_ui_signal(config_path, risk_path)
            st.success(f"Wrote {output}")
            st.code(output.read_text(encoding="utf-8"), language="yaml")
            report = output.with_name("vm_quality_lowvol_proxy_v1.alpaca.target_signal_report.md")
            if report.exists():
                st.markdown(report.read_text(encoding="utf-8"))
        except Exception as exc:
            st.error(f"Signal generation failed: {type(exc).__name__}")

with tabs[3]:
    mode = st.radio("Paper runtime mode", ["Dry-run", "Paper submit"], horizontal=True)
    interval = st.number_input("Interval seconds", min_value=5, max_value=3600, value=60, step=5)
    max_loops = st.number_input("Max loops", min_value=1, max_value=100, value=1, step=1)
    confirm = st.text_input("Paper submit confirmation")
    submit_requested = mode == "Paper submit"
    if submit_requested and confirm != "CONFIRM PAPER RUNTIME START":
        st.warning("Paper submit requires exact confirmation phrase.")
    if st.button("Start Session"):
        if submit_requested and confirm != "CONFIRM PAPER RUNTIME START":
            st.error("Confirmation phrase does not match.")
        else:
            try:
                summary = start_runtime_session(
                    submit_paper_orders=submit_requested,
                    interval_seconds=int(interval),
                    max_loops=int(max_loops),
                )
                st.success(f"Session complete: {summary['session_id']}")
                st.json(summary)
                session_dir = Path(summary["session_dir"])
                report = session_dir / "session_report.md"
                if report.exists():
                    st.markdown(report.read_text(encoding="utf-8"))
                st.code(read_tail(session_dir / "broker_errors.jsonl"), language="json")
            except Exception as exc:
                st.error(f"Runtime session failed: {type(exc).__name__}")
    if st.button("Emergency Stop"):
        stop_file = MODULE_ROOT / "evidence" / "runtime_sessions" / "EMERGENCY_STOP_LOCAL"
        stop_file.parent.mkdir(parents=True, exist_ok=True)
        stop_file.write_text("local emergency stop requested\n", encoding="utf-8")
        st.warning("Local emergency stop flag written. No liquidation or automatic cancel was submitted.")


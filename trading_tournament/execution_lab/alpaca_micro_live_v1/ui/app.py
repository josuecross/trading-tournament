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
    freeze_ready_strategies,
    generate_ui_signal,
    request_weekly_emergency_stop,
    request_weekly_stop,
    run_strategy_inventory,
    start_runtime_session,
    start_weekly_demo,
)
from execution_lab.alpaca_micro_live_v1.ui.components import status_label
from execution_lab.alpaca_micro_live_v1.ui.log_viewer import read_tail


st.set_page_config(page_title="Alpaca Micro Runtime", layout="wide")
st.title("Alpaca Micro Runtime")

tabs = st.tabs([
    "Credentials",
    "Market Clock",
    "Strategy Signal",
    "Runtime Runner",
    "Runtime Strategy Inventory",
    "Freeze Successful Strategies",
    "Weekly Demo Runner",
])

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

with tabs[4]:
    if st.button("Refresh Runtime Strategy Inventory"):
        inventory = run_strategy_inventory()
        st.json(inventory)
    inventory_path = MODULE_ROOT / "evidence" / "runtime_onboarding" / "runtime_strategy_inventory.md"
    if inventory_path.exists():
        st.markdown(inventory_path.read_text(encoding="utf-8"))

with tabs[5]:
    if st.button("Run Inventory And Freeze Ready Strategies"):
        registry = freeze_ready_strategies()
        st.success("Runtime registry updated.")
        st.json(registry)
    st.caption("Blocked strategies are not marked runtime_ready. No tournament registries or promotion files are mutated.")

with tabs[6]:
    strategy_mode = st.radio("Strategies", ["all_runtime_ready", "specific"], horizontal=True)
    specific = st.text_input("Specific strategy ids", "vm_quality_lowvol_proxy_v1")
    interval = st.number_input("Weekly interval seconds", min_value=5, max_value=86400, value=300, step=5)
    max_loops = st.number_input("Weekly max loops", min_value=1, max_value=1000, value=1, step=1)
    run_until = st.text_input("Run until ISO timestamp", "")
    resume_path = st.text_input("Resume session dir", "")
    weekly_mode = st.radio("Weekly mode", ["Dry-run", "Paper submit"], horizontal=True)
    weekly_confirm = st.text_input("Weekly paper submit confirmation")
    weekly_submit = weekly_mode == "Paper submit"
    if weekly_submit and weekly_confirm != "CONFIRM WEEKLY PAPER DEMO START":
        st.warning("Paper submit requires exact weekly confirmation phrase.")
    if st.button("Start Weekly Demo"):
        if weekly_submit and weekly_confirm != "CONFIRM WEEKLY PAPER DEMO START":
            st.error("Confirmation phrase does not match.")
        else:
            selected = ["all_runtime_ready"] if strategy_mode == "all_runtime_ready" else [item.strip() for item in specific.split(",") if item.strip()]
            try:
                summary = start_weekly_demo(
                    strategies=selected,
                    submit_paper_orders=weekly_submit,
                    interval_seconds=int(interval),
                    max_loops=int(max_loops),
                    run_until=run_until or None,
                    resume=Path(resume_path) if resume_path else None,
                )
                st.success(f"Weekly session: {summary['session_dir']}")
                st.json(summary)
                session_dir = Path(summary["session_dir"])
                for name in ["weekly_summary.md", "broker_errors.jsonl", "submitted_orders.jsonl", "open_orders.jsonl"]:
                    path = session_dir / name
                    if path.exists():
                        st.subheader(name)
                        st.code(read_tail(path), language="json" if path.suffix == ".jsonl" else "markdown")
            except Exception as exc:
                st.error(f"Weekly demo failed: {type(exc).__name__}")
    c1, c2 = st.columns(2)
    if c1.button("Stop Weekly Demo"):
        st.warning(f"Stop file written: {request_weekly_stop()}")
    if c2.button("Emergency Stop Weekly Demo"):
        st.warning(f"Emergency stop file written: {request_weekly_emergency_stop()}. No liquidation/cancel submitted.")


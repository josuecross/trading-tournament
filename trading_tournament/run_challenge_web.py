from __future__ import annotations

import argparse
import csv
import html
import json
import mimetypes
import re
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import yaml


REPO_ROOT = Path(__file__).resolve().parent
CHALLENGE_ROOT = REPO_ROOT / "evidence" / "challenge_runs"
LATEST_DIR = CHALLENGE_ROOT / "latest"
LATEST_ZIP = CHALLENGE_ROOT / "latest_challenge_packet.zip"
RUNNER = REPO_ROOT / "run_challenge_audit.py"
ALLOWED_MODES = {"research_sample", "candidate_exhaustive"}
ALLOWED_LATEST_FILES = {
    "README_FOR_AUDITOR.md",
    "challenge_summary.md",
    "challenge_results.csv",
    "rolling_window_summary.csv",
    "strategy_rankings.csv",
    "assumptions_and_costs.yaml",
    "data_coverage_summary.csv",
    "risk_and_stop_audit.csv",
    "warnings_and_limitations.md",
    "challenge_charts.png",
}
FINALIST_RE = re.compile(r"^[A-Za-z0-9_,.-]+$")


@dataclass
class JobState:
    state: str = "idle"
    command: list[str] = field(default_factory=list)
    started_at_utc: str = ""
    finished_at_utc: str = ""
    return_code: int | None = None
    log: list[str] = field(default_factory=list)
    error: str = ""


class ChallengeRunManager:
    def __init__(self, repo_root: Path = REPO_ROOT) -> None:
        self.repo_root = repo_root
        self._lock = threading.Lock()
        self._job = JobState()
        self._process: subprocess.Popen[str] | None = None

    def status(self) -> dict[str, Any]:
        with self._lock:
            elapsed_seconds = elapsed_time_seconds(self._job.started_at_utc, "" if self._job.state == "running" else self._job.finished_at_utc)
            duration_seconds = elapsed_time_seconds(self._job.started_at_utc, self._job.finished_at_utc)
            job = {
                "state": self._job.state,
                "command": self._job.command,
                "started_at_utc": self._job.started_at_utc,
                "finished_at_utc": self._job.finished_at_utc,
                "elapsed_seconds": elapsed_seconds,
                "duration_seconds": duration_seconds,
                "return_code": self._job.return_code,
                "log_tail": self._job.log[-120:],
                "error": self._job.error,
            }
        return {"job": job, "latest": latest_artifacts_summary(self.repo_root)}

    def start(self, options: dict[str, Any]) -> dict[str, Any]:
        command = build_runner_command(options, python_executable=sys.executable, repo_root=self.repo_root)
        with self._lock:
            if self._job.state == "running":
                raise ValueError("A challenge run is already running.")
            self._job = JobState(
                state="running",
                command=command,
                started_at_utc=utc_now(),
                log=[],
            )
        thread = threading.Thread(target=self._run_command, args=(command,), daemon=True)
        thread.start()
        return self.status()

    def _append_log(self, line: str) -> None:
        with self._lock:
            self._job.log.append(line.rstrip())
            if len(self._job.log) > 500:
                self._job.log = self._job.log[-500:]

    def _run_command(self, command: list[str]) -> None:
        try:
            process = subprocess.Popen(
                command,
                cwd=self.repo_root,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
            )
            with self._lock:
                self._process = process
            assert process.stdout is not None
            for line in process.stdout:
                self._append_log(line)
            return_code = process.wait()
            with self._lock:
                self._job.return_code = return_code
                self._job.finished_at_utc = utc_now()
                self._job.state = "succeeded" if return_code == 0 else "failed"
                if return_code != 0:
                    self._job.error = f"run_challenge_audit.py exited with code {return_code}"
                self._process = None
        except Exception as exc:  # pragma: no cover - defensive thread boundary
            with self._lock:
                self._job.state = "failed"
                self._job.finished_at_utc = utc_now()
                self._job.error = str(exc)
                self._process = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_utc(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def elapsed_time_seconds(started_at_utc: str, finished_at_utc: str = "") -> int:
    started = parse_utc(started_at_utc)
    if started is None:
        return 0
    finished = parse_utc(finished_at_utc) or datetime.now(timezone.utc)
    return max(0, int((finished - started).total_seconds()))


def bool_option(options: dict[str, Any], key: str, default: bool) -> bool:
    value = options.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def int_option(options: dict[str, Any], key: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(options.get(key, default))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def clean_finalists(value: Any, mode: str) -> str:
    finalists = str(value or "").strip()
    if not finalists and mode == "candidate_exhaustive":
        return "current_no_cash_proxy_alpha_AB"
    if not finalists:
        return ""
    finalists = finalists.replace(" ", "")
    if not FINALIST_RE.match(finalists):
        raise ValueError("Finalists may only contain letters, numbers, underscores, commas, periods, and hyphens.")
    return finalists


def build_runner_command(options: dict[str, Any], python_executable: str = sys.executable, repo_root: Path = REPO_ROOT) -> list[str]:
    mode = str(options.get("mode", "research_sample"))
    if mode not in ALLOWED_MODES:
        raise ValueError(f"Unsupported mode: {mode}")

    finalists = clean_finalists(options.get("finalists", ""), mode)
    include_etf = bool_option(options, "include_etf", True)
    include_benchmarks = bool_option(options, "include_benchmarks", True)
    include_crypto = bool_option(options, "include_crypto", mode == "research_sample")
    include_leverage = bool_option(options, "include_leverage", mode == "research_sample")
    no_network = bool_option(options, "no_network", False)
    reuse_cache = bool_option(options, "reuse_cache", True)
    max_runtime = int_option(options, "max_runtime_minutes", 45, 1, 240)

    command = [
        python_executable,
        str(repo_root / "run_challenge_audit.py"),
        "--mode",
        mode,
    ]
    if finalists:
        command.extend(["--finalists", finalists])
    command.append("--include-etf" if include_etf else "--no-etf")
    command.append("--include-benchmarks" if include_benchmarks else "--no-benchmarks")
    command.append("--include-crypto" if include_crypto else "--no-crypto")
    command.append("--include-leverage" if include_leverage else "--no-leverage")
    command.append("--reuse-cache" if reuse_cache else "--no-reuse-cache")
    if no_network:
        command.append("--no-network")
    command.extend(["--max-runtime-minutes", str(max_runtime)])
    return command


def read_csv_rows(path: Path, limit: int | None = None) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return rows[:limit] if limit else rows


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def latest_artifacts_summary(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    latest_dir = repo_root / "evidence" / "challenge_runs" / "latest"
    latest_zip = repo_root / "evidence" / "challenge_runs" / "latest_challenge_packet.zip"
    assumptions = read_yaml(latest_dir / "assumptions_and_costs.yaml")
    challenge_rows = read_csv_rows(latest_dir / "challenge_results.csv")
    ranking_rows = read_csv_rows(latest_dir / "strategy_rankings.csv", limit=8)
    rolling_rows = read_csv_rows(latest_dir / "rolling_window_summary.csv")
    files = sorted(p.name for p in latest_dir.iterdir() if p.is_file()) if latest_dir.exists() else []
    run_id = challenge_rows[0].get("run_id", "") if challenge_rows else ""

    focus = {"current_no_cash_proxy_alpha_AB", "SPY_buy_hold", "SPY_200d_trend_model", "BIL_cash_proxy"}
    comparison_90d = [
        {
            "strategy": row.get("strategy", ""),
            "label": row.get("standard_or_stress", ""),
            "plus300": row.get("pct_target_300_before_stop", ""),
            "plus400": row.get("pct_target_400_before_stop", ""),
            "stop": row.get("pct_any_project_stop_hit", ""),
            "method": row.get("rolling_method", ""),
            "windows": row.get("number_of_windows", ""),
            "possible": row.get("possible_window_count", ""),
            "final": row.get("sampled_results_are_final", ""),
        }
        for row in rolling_rows
        if row.get("strategy") in focus and str(row.get("horizon")) == "90"
    ]

    return {
        "exists": latest_dir.exists(),
        "run_id": run_id,
        "file_count": len(files),
        "files": files,
        "zip_exists": latest_zip.exists(),
        "zip_path": str(latest_zip),
        "validation": assumptions.get("validation", {}),
        "lanes": assumptions.get("lanes", {}),
        "leverage": assumptions.get("leverage", {}),
        "top_rankings": ranking_rows,
        "comparison_90d": comparison_90d,
    }


HTML_PAGE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Challenge Audit Runner</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --ink: #17202a;
      --muted: #697586;
      --line: #d7dde5;
      --accent: #136f63;
      --danger: #a43d3d;
      --warn: #8a6200;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--bg);
    }
    header {
      padding: 18px 24px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }
    h1 { font-size: 18px; margin: 0; letter-spacing: 0; }
    main {
      display: grid;
      grid-template-columns: minmax(320px, 420px) 1fr;
      gap: 16px;
      padding: 16px;
      max-width: 1320px;
      margin: 0 auto;
    }
    section {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }
    h2 { font-size: 15px; margin: 0 0 12px; }
    label { display: block; color: var(--muted); font-weight: 600; margin: 12px 0 6px; }
    select, input[type="text"], input[type="number"] {
      width: 100%;
      height: 38px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 0 10px;
      font: inherit;
      background: #fff;
      color: var(--ink);
    }
    .checks {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px 12px;
      margin-top: 8px;
    }
    .checks label {
      display: flex;
      gap: 8px;
      align-items: center;
      margin: 0;
      color: var(--ink);
      font-weight: 500;
    }
    .buttons { display: flex; gap: 10px; margin-top: 16px; flex-wrap: wrap; }
    button, a.button {
      border: 1px solid transparent;
      border-radius: 6px;
      min-height: 38px;
      padding: 0 14px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      color: #fff;
      background: var(--accent);
      font-weight: 700;
      text-decoration: none;
      cursor: pointer;
    }
    button.secondary, a.secondary { color: var(--ink); background: #fff; border-color: var(--line); }
    button:disabled { opacity: .55; cursor: wait; }
    .status {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 10px;
      border-radius: 999px;
      background: #eef4f2;
      color: var(--accent);
      font-weight: 700;
    }
    .status.failed { color: var(--danger); background: #fff0f0; }
    .status.running { color: var(--warn); background: #fff7df; }
    .progress {
      margin-top: 14px;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfd;
    }
    .progress.hidden { display: none; }
    .progress-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 10px;
    }
    .progress-left {
      display: flex;
      align-items: center;
      gap: 9px;
      font-weight: 700;
    }
    .spinner {
      width: 18px;
      height: 18px;
      border: 3px solid #d9e2e0;
      border-top-color: var(--accent);
      border-radius: 50%;
      animation: spin .8s linear infinite;
    }
    .progress-track {
      height: 9px;
      overflow: hidden;
      border-radius: 999px;
      background: #e8edf2;
    }
    .progress-bar {
      width: 45%;
      height: 100%;
      border-radius: 999px;
      background: repeating-linear-gradient(45deg, var(--accent), var(--accent) 10px, #1f8b7d 10px, #1f8b7d 20px);
      animation: slide 1.2s ease-in-out infinite alternate;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    @keyframes slide { from { transform: translateX(-80%); } to { transform: translateX(155%); } }
    .grid { display: grid; gap: 16px; }
    table { width: 100%; border-collapse: collapse; }
    th, td { padding: 8px; border-bottom: 1px solid var(--line); text-align: left; white-space: nowrap; }
    th { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .03em; }
    .table-wrap { overflow-x: auto; }
    .muted { color: var(--muted); }
    pre {
      max-height: 240px;
      overflow: auto;
      margin: 0;
      padding: 12px;
      border-radius: 6px;
      background: #101820;
      color: #d8f3dc;
      white-space: pre-wrap;
    }
    .files {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .files a {
      color: var(--accent);
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 5px 9px;
      text-decoration: none;
      background: #fff;
    }
    img {
      max-width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
    }
    @media (max-width: 860px) {
      main { grid-template-columns: 1fr; }
      header { align-items: flex-start; flex-direction: column; }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Challenge Audit Runner</h1>
      <div class="muted">Local paper/demo research only. No broker, no live orders, no real-money recommendation.</div>
    </div>
    <span id="state" class="status">idle</span>
  </header>

  <main>
    <section>
      <h2>Run</h2>
      <label for="mode">Mode</label>
      <select id="mode">
        <option value="research_sample">research_sample</option>
        <option value="candidate_exhaustive">candidate_exhaustive</option>
      </select>

      <label for="finalists">Finalist</label>
      <input id="finalists" type="text" value="current_no_cash_proxy_alpha_AB">

      <label>Lanes</label>
      <div class="checks">
        <label><input id="include_etf" type="checkbox" checked> ETF</label>
        <label><input id="include_benchmarks" type="checkbox" checked> Benchmarks</label>
        <label><input id="include_crypto" type="checkbox" checked> Crypto</label>
        <label><input id="include_leverage" type="checkbox" checked> Leverage</label>
      </div>

      <label>Run Options</label>
      <div class="checks">
        <label><input id="reuse_cache" type="checkbox" checked> Reuse cache</label>
        <label><input id="no_network" type="checkbox"> No network</label>
      </div>

      <label for="max_runtime_minutes">Max runtime minutes</label>
      <input id="max_runtime_minutes" type="number" min="1" max="240" value="45">

      <div class="buttons">
        <button id="run">Start Run</button>
        <button id="refresh" class="secondary">Refresh</button>
        <a id="download" class="button secondary" href="/download/latest_challenge_packet.zip">Download Zip</a>
      </div>
      <div id="progress" class="progress hidden" aria-live="polite">
        <div class="progress-row">
          <div class="progress-left">
            <span id="spinner" class="spinner" aria-hidden="true"></span>
            <span id="progress_label">Idle</span>
          </div>
          <span id="elapsed" class="muted">00:00</span>
        </div>
        <div class="progress-track"><div id="progress_bar" class="progress-bar"></div></div>
      </div>
    </section>

    <div class="grid">
      <section>
        <h2>Latest</h2>
        <div id="latest" class="muted">Loading...</div>
      </section>

      <section>
        <h2>90-Day Comparison</h2>
        <div class="table-wrap">
          <table>
            <thead><tr><th>Strategy</th><th>Label</th><th>+300</th><th>+400</th><th>Stop</th><th>Method</th><th>Windows</th><th>Final</th></tr></thead>
            <tbody id="comparison"></tbody>
          </table>
        </div>
      </section>

      <section>
        <h2>Rankings</h2>
        <div class="table-wrap">
          <table>
            <thead><tr><th>Rank</th><th>Strategy</th><th>Verdict</th><th>+300 90d</th><th>+400 90d</th><th>Stop 90d</th></tr></thead>
            <tbody id="rankings"></tbody>
          </table>
        </div>
      </section>

      <section>
        <h2>Files</h2>
        <div id="files" class="files"></div>
      </section>

      <section>
        <h2>Log</h2>
        <pre id="log"></pre>
      </section>

      <section>
        <h2>Chart</h2>
        <img id="chart" alt="Challenge chart" src="/latest/challenge_charts.png">
      </section>
    </div>
  </main>

<script>
const $ = (id) => document.getElementById(id);
let lastJob = {};

function pct(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "";
  return (n * 100).toFixed(1) + "%";
}

function duration(seconds) {
  const total = Math.max(0, Math.floor(Number(seconds) || 0));
  const hours = Math.floor(total / 3600);
  const mins = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  const mm = String(mins).padStart(2, "0");
  const ss = String(secs).padStart(2, "0");
  return hours ? `${hours}:${mm}:${ss}` : `${mm}:${ss}`;
}

function applyModeDefaults() {
  if ($("mode").value === "candidate_exhaustive") {
    $("include_etf").checked = true;
    $("include_benchmarks").checked = true;
    $("include_crypto").checked = false;
    $("include_leverage").checked = false;
    $("max_runtime_minutes").value = "45";
  }
}

function payload() {
  return {
    mode: $("mode").value,
    finalists: $("finalists").value,
    include_etf: $("include_etf").checked,
    include_benchmarks: $("include_benchmarks").checked,
    include_crypto: $("include_crypto").checked,
    include_leverage: $("include_leverage").checked,
    reuse_cache: $("reuse_cache").checked,
    no_network: $("no_network").checked,
    max_runtime_minutes: Number($("max_runtime_minutes").value || 45)
  };
}

async function startRun() {
  $("run").disabled = true;
  const res = await fetch("/api/run", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload())
  });
  const data = await res.json();
  if (!res.ok) alert(data.error || "Could not start run");
  render(data);
}

async function refresh() {
  const res = await fetch("/api/status");
  render(await res.json());
}

function render(data) {
  const job = data.job || {};
  lastJob = job;
  const latest = data.latest || {};
  const state = job.state || "idle";
  const seconds = state === "running" ? job.elapsed_seconds : job.duration_seconds;
  $("state").textContent = state === "running" ? `${state} • ${duration(seconds)}` : state;
  $("state").className = "status " + state;
  $("run").disabled = state === "running";
  $("log").textContent = (job.log_tail || []).join("\n");
  $("progress").classList.toggle("hidden", state !== "running" && !job.started_at_utc);
  $("progress_label").textContent = state === "running" ? "Running challenge audit" : (state === "idle" ? "Idle" : `Last run ${state}`);
  $("elapsed").textContent = state === "running" ? `Elapsed ${duration(job.elapsed_seconds)}` : `Duration ${duration(job.duration_seconds)}`;
  $("spinner").style.display = state === "running" ? "inline-block" : "none";
  $("progress_bar").style.animationPlayState = state === "running" ? "running" : "paused";

  const validation = latest.validation || {};
  const lanes = latest.lanes || {};
  $("latest").innerHTML = `
    <strong>run_id:</strong> ${latest.run_id || "none"}<br>
    <strong>mode:</strong> ${validation.mode || "unknown"}<br>
    <strong>final_validation_completed:</strong> ${validation.final_validation_completed ?? ""}<br>
    <strong>sampled_results_are_final:</strong> ${validation.sampled_results_are_final ?? ""}<br>
    <strong>lanes:</strong> ETF=${lanes.include_etf ?? ""}, Benchmarks=${lanes.include_benchmarks ?? ""}, Crypto=${lanes.include_crypto ?? ""}<br>
    <strong>file_count:</strong> ${latest.file_count || 0}<br>
    <strong>zip:</strong> ${latest.zip_exists ? "available" : "missing"}
  `;

  $("comparison").innerHTML = (latest.comparison_90d || []).map(row => `
    <tr><td>${row.strategy}</td><td>${row.label}</td><td>${pct(row.plus300)}</td><td>${pct(row.plus400)}</td><td>${pct(row.stop)}</td><td>${row.method}</td><td>${row.windows}/${row.possible}</td><td>${row.final}</td></tr>
  `).join("");

  $("rankings").innerHTML = (latest.top_rankings || []).map(row => `
    <tr><td>${row.rank_overall || ""}</td><td>${row.strategy || ""}</td><td>${row.audit_verdict || ""}</td><td>${pct(row.pct_90d_target_300_before_stop)}</td><td>${pct(row.pct_90d_target_400_before_stop)}</td><td>${pct(row.pct_90d_any_stop_hit)}</td></tr>
  `).join("");

  $("files").innerHTML = (latest.files || []).map(name => `<a href="/latest/${encodeURIComponent(name)}" target="_blank">${name}</a>`).join("");
  $("download").style.pointerEvents = latest.zip_exists ? "auto" : "none";
  $("download").style.opacity = latest.zip_exists ? "1" : ".5";
  $("chart").src = "/latest/challenge_charts.png?ts=" + Date.now();
}

$("run").addEventListener("click", startRun);
$("refresh").addEventListener("click", refresh);
$("mode").addEventListener("change", applyModeDefaults);
applyModeDefaults();
refresh();
setInterval(() => {
  if ((lastJob.state || "") === "running") refresh();
}, 1000);
setInterval(refresh, 5000);
</script>
</body>
</html>
"""


class ChallengeWebHandler(BaseHTTPRequestHandler):
    manager: ChallengeRunManager

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/":
                self.send_text(HTML_PAGE, "text/html; charset=utf-8")
            elif parsed.path == "/api/status":
                self.send_json(self.manager.status())
            elif parsed.path == "/api/latest":
                self.send_json(latest_artifacts_summary(REPO_ROOT))
            elif parsed.path == "/download/latest_challenge_packet.zip":
                self.send_file(LATEST_ZIP, download_name="latest_challenge_packet.zip")
            elif parsed.path.startswith("/latest/"):
                name = unquote(parsed.path.removeprefix("/latest/"))
                if name not in ALLOWED_LATEST_FILES:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                self.send_file(LATEST_DIR / name)
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except Exception as exc:  # pragma: no cover - HTTP boundary
            self.send_json({"error": str(exc)}, status=500)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/api/run":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8") if length else "{}"
            options = json.loads(raw)
            status = self.manager.start(options)
            self.send_json(status, status=202)
        except ValueError as exc:
            self.send_json({"error": str(exc), **self.manager.status()}, status=400)
        except json.JSONDecodeError:
            self.send_json({"error": "Invalid JSON body."}, status=400)

    def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, indent=2, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_text(self, text: str, content_type: str, status: int = 200) -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path: Path, download_name: str | None = None) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if download_name:
            self.send_header("Content-Disposition", f'attachment; filename="{html.escape(download_name)}"')
        self.end_headers()
        self.wfile.write(body)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local web UI for compact challenge audit runs.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not RUNNER.exists():
        raise SystemExit(f"Missing runner: {RUNNER}")
    if not shutil.which(sys.executable):
        raise SystemExit(f"Python executable is unavailable: {sys.executable}")
    manager = ChallengeRunManager(REPO_ROOT)
    ChallengeWebHandler.manager = manager
    server = ThreadingHTTPServer((args.host, args.port), ChallengeWebHandler)
    url = f"http://{args.host}:{args.port}"
    print(f"challenge_web_url={url}", flush=True)
    print("research_only=true", flush=True)
    print("real_money_recommendation=false", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nserver_stopped=true")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

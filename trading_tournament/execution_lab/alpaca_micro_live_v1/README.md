# Alpaca Micro Live V1

This is an isolated Alpaca paper/demo runtime module. Trading Tournament remains the research/discovery engine; this module only runs frozen runtime copies of strategies that were already researched elsewhere.

One-way connection:

```text
researched/promoted strategy
-> copied frozen runtime spec
-> Alpaca historical data signal
-> Alpaca paper/demo execution
```

This module does not import tournament research runners, use tournament cache, mutate registries, change promotion reviews, change paper-forward observations, or submit live orders.

## Windows Setup

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pandas numpy pyyaml requests pytest streamlit
```

If activation is blocked:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Local Secrets

Create `.env.local` in the repository root.

```env
ALPACA_PAPER_API_KEY=your_paper_key
ALPACA_PAPER_SECRET_KEY=your_paper_secret
```

Optional live variables may be detected, but live execution is disabled:

```env
ALPACA_LIVE_API_KEY=not_used
ALPACA_LIVE_SECRET_KEY=not_used
```

Secrets are masked in output and must not be committed.

## Local Configs

Create local configs from examples:

```powershell
Copy-Item execution_lab\alpaca_micro_live_v1\config\alpaca_paper.example.yaml execution_lab\alpaca_micro_live_v1\config\alpaca_paper.local.yaml
Copy-Item execution_lab\alpaca_micro_live_v1\config\risk_limits.example.yaml execution_lab\alpaca_micro_live_v1\config\risk_limits.local.yaml
```

Example/local config files are separated so local runtime choices are not committed.

## Credential Check

```powershell
python -m execution_lab.alpaca_micro_live_v1.execution.check_credentials --environment paper
```

Connectivity requires explicit opt-in; the default command is local-only and does not call Alpaca:

```powershell
python -m execution_lab.alpaca_micro_live_v1.execution.check_credentials --environment paper --network
```

## Market Clock

```powershell
python -m execution_lab.alpaca_micro_live_v1.execution.market_clock_check `
  --config execution_lab\alpaca_micro_live_v1\config\alpaca_paper.local.yaml
```

## Signal Generation

```powershell
python -m execution_lab.alpaca_micro_live_v1.signals.generate_alpaca_signal `
  --strategy-id vm_quality_lowvol_proxy_v1 `
  --config execution_lab\alpaca_micro_live_v1\config\alpaca_paper.local.yaml `
  --risk-limits execution_lab\alpaca_micro_live_v1\config\risk_limits.local.yaml `
  --output execution_lab\alpaca_micro_live_v1\evidence\alpaca_signals\vm_quality_lowvol_proxy_v1.alpaca.target.yaml
```

The target source is `alpaca_runtime`, and the signal uses Alpaca daily bars, not tournament cache.

## Runtime Dry-Run

Dry-run is the default and submits nothing:

```powershell
python -m execution_lab.alpaca_micro_live_v1.execution.runtime_orchestrator `
  --config execution_lab\alpaca_micro_live_v1\config\alpaca_paper.local.yaml `
  --risk-limits execution_lab\alpaca_micro_live_v1\config\risk_limits.local.yaml `
  --runtime-registry execution_lab\alpaca_micro_live_v1\runtime_strategies\runtime_strategy_registry.yaml `
  --strategies vm_quality_lowvol_proxy_v1 `
  --mode paper `
  --interval-seconds 60 `
  --max-loops 2 `
  --dry-run
```

## Runtime Paper Submit

Paper submit requires an explicit flag. There is no live submit command.

```powershell
python -m execution_lab.alpaca_micro_live_v1.execution.runtime_orchestrator `
  --config execution_lab\alpaca_micro_live_v1\config\alpaca_paper.local.yaml `
  --risk-limits execution_lab\alpaca_micro_live_v1\config\risk_limits.local.yaml `
  --runtime-registry execution_lab\alpaca_micro_live_v1\runtime_strategies\runtime_strategy_registry.yaml `
  --strategies vm_quality_lowvol_proxy_v1 `
  --mode paper `
  --interval-seconds 60 `
  --max-loops 2 `
  --submit-paper-orders
```

The loop can wake every minute, but the strategy signal is based on daily completed bars. Target-version idempotency prevents repeated duplicate submits for the same target within a session.

## Successful Strategy Inventory

Inventory successful local Trading Tournament strategies before onboarding them:

```powershell
python -m execution_lab.alpaca_micro_live_v1.execution.runtime_strategy_inventory
```

The inventory writes:

```text
execution_lab/alpaca_micro_live_v1/evidence/runtime_onboarding/runtime_strategy_inventory.json
execution_lab/alpaca_micro_live_v1/evidence/runtime_onboarding/runtime_strategy_inventory.md
```

Classifications are conservative:

- `runtime_ready`: already copied into this Alpaca runtime with local spec and module.
- `ready_to_freeze`: successful/approved local evidence plus fully recoverable ETF/stock rules.
- `onboarding_blocked`: successful or promising, but exact runtime rules are incomplete or not validated enough.
- `not_successful_enough`: future research, watchlist, or review-only evidence.
- `unsupported_asset_class`: outside current stock/ETF paper runtime.

Future-research-only variants are not runtime-ready.

## Freeze Successful Strategies

Freeze ready strategies into the Alpaca runtime:

```powershell
python -m execution_lab.alpaca_micro_live_v1.execution.freeze_successful_strategies `
  --inventory execution_lab\alpaca_micro_live_v1\evidence\runtime_onboarding\runtime_strategy_inventory.json `
  --output-registry execution_lab\alpaca_micro_live_v1\runtime_strategies\runtime_strategy_registry.yaml
```

Frozen strategies get a YAML spec, Python target generator, and source trace under `execution_lab/alpaca_micro_live_v1/runtime_strategies/`.

Blocked strategies may appear in the runtime registry only with:

```yaml
enabled: false
runtime_ready: false
blocked_reason: ...
```

The freeze command does not mutate tournament registries, promotion reviews, paper-forward observations, or frozen controls.

## Weekly Paper/Demo Observation

Dry-run is the default:

```powershell
python -m execution_lab.alpaca_micro_live_v1.execution.weekly_demo_runner `
  --config execution_lab\alpaca_micro_live_v1\config\alpaca_paper.local.yaml `
  --risk-limits execution_lab\alpaca_micro_live_v1\config\risk_limits.local.yaml `
  --runtime-registry execution_lab\alpaca_micro_live_v1\runtime_strategies\runtime_strategy_registry.yaml `
  --strategies all_runtime_ready `
  --mode paper `
  --interval-seconds 300 `
  --duration-days 7 `
  --dry-run
```

Paper submit requires `--submit-paper-orders`; live mode is unsupported. If runtime-ready strategies share symbols and no `multi_strategy_allocation_policy: independent_sleeves` policy exists, weekly paper submit fails closed. Dry-run still writes inventory/reporting evidence.

Resume:

```powershell
python -m execution_lab.alpaca_micro_live_v1.execution.weekly_demo_runner `
  --resume execution_lab\alpaca_micro_live_v1\evidence\weekly_demo_sessions\weekly_demo_<timestamp>
```

Stop files:

```text
execution_lab/alpaca_micro_live_v1/evidence/control/STOP_WEEKLY_DEMO
execution_lab/alpaca_micro_live_v1/evidence/control/EMERGENCY_STOP_WEEKLY_DEMO
```

Emergency stop does not liquidate, sell all, or automatically cancel orders.

## Weekly Audit Dataset

Weekly sessions are written to:

```text
execution_lab/alpaca_micro_live_v1/evidence/weekly_demo_sessions/weekly_demo_<timestamp>/
```

The runner records session metadata, config/registry/spec hashes, strategy signals, eligibility/ranking snapshots, target weights, account and position snapshots, proposed/skipped/submitted orders, risk-gate decisions, allocation drift, performance snapshots, execution quality, daily summaries, and weekly summaries.

Skips such as `within_tolerance`, `target_version_already_handled`, `market_closed_submit_blocked`, and `no_actionable_delta` are written to `skipped_orders.jsonl` or `runtime_blocks.jsonl`, not broker rejects.

## GUI

```powershell
streamlit run execution_lab\alpaca_micro_live_v1\ui\app.py --server.address 127.0.0.1
```

The GUI includes tabs for credentials, market clock, signal generation, runtime runner, runtime strategy inventory, freeze successful strategies, and weekly demo runner.

Weekly paper submit requires the exact phrase:

```text
CONFIRM WEEKLY PAPER DEMO START
```

There is no live start button.

## Evidence

Runtime evidence is written under:

```text
execution_lab/alpaca_micro_live_v1/evidence/
```

Session folders include state, loop events, signals, proposed orders, submitted orders, rejects, broker errors, summaries, and a session report.

## Broker Errors

Read-only calls can retry bounded transient failures. Order submit is never blindly retried. If a submit fails with a network/5xx/unknown error, the runtime records the `client_order_id`, marks the submission ambiguous when appropriate, fails closed, and requires manual review before any retry.

## Stop / Emergency Stop

Stop and emergency stop are local runtime/session controls only. They do not liquidate, sell all, or automatically cancel orders.

## Tests

Run only the Alpaca module tests:

```powershell
$testFiles = Get-ChildItem tests\test_alpaca_micro_live_*.py | Select-Object -ExpandProperty FullName
python -m pytest $testFiles -q
```

The tests use fake Alpaca responses and make no real network calls.


# React CCRS Experiment Reports

This directory contains the manual-first report pipeline for React CCRS maze
runs. It mirrors the BDI experiment package shape where the data is comparable,
while documenting React-specific advisory prompt metrics instead of BDI
deterministic option-reordering metrics.

## Manual Workflow

Run commands from the repository root.

```powershell
powershell -ExecutionPolicy Bypass -File experiments\scripts\prepare-current-run.ps1
```

Run the agent manually, for example:

```powershell
S:\anaconda\agent\python.exe main.py --graph-name graph --agent-name react_baseline_1 --log-level INFO
```

Export MASE viewer events into [runs/latest](runs/latest), then import the run:

```powershell
powershell -ExecutionPolicy Bypass -File experiments\scripts\import-manual-run.ps1 `
  -BatchId react-baseline-vs-ccrs-v1 `
  -RunId 001-baseline `
  -AgentName react_baseline_1 `
  -GraphName graph `
  -ReactLog logs\<baseline-log>.log
```

Repeat staging, running, MASE export, and import for the CCRS agent:

```powershell
powershell -ExecutionPolicy Bypass -File experiments\scripts\prepare-current-run.ps1

S:\anaconda\agent\python.exe main.py --graph-name graph_ccrs --enable-contingency-escalation-tool --agent-name react_ccrs_1 --log-level INFO

powershell -ExecutionPolicy Bypass -File experiments\scripts\import-manual-run.ps1 `
  -BatchId react-baseline-vs-ccrs-v1 `
  -RunId 002-ccrs `
  -AgentName react_ccrs_1 `
  -GraphName graph_ccrs `
  -EnableContingencyEscalationTool `
  -ReactLog logs\<ccrs-log>.log `
  -JavaLog logs\<ccrs-log>.java.log
```

Generate the report. This refreshes normalized CSV artifacts first, then writes
`summary.md` and `summary.json`:

```powershell
powershell -ExecutionPolicy Bypass -File experiments\scripts\write-report.ps1 -BatchId react-baseline-vs-ccrs-v1
```

## Run Package Shape

[scripts/import-manual-run.ps1](scripts/import-manual-run.ps1) writes each run
under `experiments/runs/<batch-id>/<run-id>/`.

- `run.json`: run metadata, graph name, agent name, imported log names, MASE
  capture status, and optional scenario fields.
- `mase-events.jsonl`: normalized MASE viewer export, when present.
- `source-exports/`: original MASE exports and staging metadata.
- `<run>.log`: copied React log.
- `<run>.java.log`: copied Java companion log when provided.
- `manifest.json`: batch-level manifest refreshed after every import.

React logs passed through `-ReactLog` and `-JavaLog` are copied into the run
package. Staged MASE exports are moved out of `latest` unless `-KeepSource`
is supplied.

## CSV Artifacts

[scripts/parse-experiment-logs.ps1](scripts/parse-experiment-logs.ps1) writes
CSV files into `experiments/reports/<batch-id>/`.

- `runs.csv`: one row per imported run with graph metadata, MASE counts, React
  CCRS event counts, Java evidence counts, and `decision_metric_quality`.
- `agents.csv`: one row per imported experiment agent observed in MASE, with
  movement count and final cell.
- `mase-events.csv`: normalized MASE event rows filtered to the imported
  experiment agent.
- `mase-agent-moved.csv`: normalized `AGENT_MOVED` rows filtered to the imported
  experiment agent.
- `mase-transactions.csv`: normalized MASE transaction rows filtered to the
  imported experiment agent.
- `cycle-durations.csv`: React cycle rows derived from structured CCRS cycle
  timestamps.
- `decisions.csv`: one row per `react.ccrs.opportunistic.selection` event.
- `advisory-follow.csv`: aggregate opportunistic CCRS rank-follow buckets
  derived from `decisions.csv` and `opportunistic.csv`.
- `contingency.csv`: React contingency CCRS and contingency-produced guidance
  events.
- `opportunistic.csv`: React opportunistic CCRS lifecycle events.
- `actions.csv`: parsed tool invocations from `[TOOL_NODE]` log lines. Fresh
  runs also populate tool result fields such as `tool_call_id`, `http_status`,
  `http_ok`, `response_length`, and error details.
- `move-action-correlation.csv`: action windows keyed by successful movement
  POSTs matched to filtered MASE `AGENT_MOVED` rows.
- `java-library-evidence.csv`: Java companion log evidence, kept separate from
  React adapter decisions.
- `path-analysis-inputs/*.cells.txt`: movement paths grouped by run and MASE
  agent.
- `summary.json`: parser/report metadata and aggregate artifact counts.
- `summary.md`: first-version Markdown report.

Metric definitions are maintained separately in [METRICS.md](METRICS.md).

## React Advisory Metrics

BDI reports use JaCaMo adapter events such as `ccrs.opportunistic.prioritize`
to measure deterministic option reordering and strict overrules. React CCRS does
not reorder deterministic AgentSpeak options. It injects advisory prompt context
and then observes the LLM-selected tool call.

React v1 reports therefore use advisory-follow fields in `decisions.csv`:

- `opportunistic_count`: number of prompt-visible opportunistic CCRS entries.
- `contingency_guidance_count`: number of prompt-visible
  contingency-produced opportunistic guidance entries.
- `top_opportunistic_target`: highest-utility opportunistic target visible in
  the prompt.
- `top_contingency_guidance_target`: highest-ranked contingency-produced target
  visible in the prompt.
- `followed_top_opportunistic`: selected tool URL exactly matched the top
  opportunistic target.
- `followed_top_contingency_guidance`: selected tool URL exactly matched the top
  contingency-produced target.
- `followed_any_top_guidance`: either channel-specific followed flag is true.

The per-count rank buckets are written to `advisory-follow.csv`. For each run
and each observed `opportunistic_count`, the report counts selections of rank 1
(highest utility), rank 2, rank 3, and so on up to the maximum observed count.
It also counts selections that matched none of the same-cycle opportunistic
targets. The rank order is inferred from `opportunistic.csv` detection rows in
the same run and cycle, sorted by descending `utility`.

Older logs that predate `react.ccrs.opportunistic.selection` remain parseable,
but `decisions.csv` will be empty and `runs.csv` will mark
`decision_metric_quality=missing_selection_event`.

## Required React Events

The report parser reads structured React events emitted by
[audit.py](../react_agent/ccrs/audit.py). The reportability events added for
advisory-follow metrics are:

- `react.ccrs.prompt_context.visible`: emitted before the LLM call when any
  CCRS context is visible in the prompt.
- `react.ccrs.opportunistic.selection`: emitted after the LLM response for each
  selected tool call.

The parser also reads existing opportunistic, contingency, and
contingency-produced guidance events documented in
[react_agent/ccrs/README.md](../react_agent/ccrs/README.md).

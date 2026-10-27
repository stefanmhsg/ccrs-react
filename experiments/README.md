# React CCRS Experiment Reports

Current import/report code and synthetic tests are maintained in
[ccrs-experiments](../../ccrs-experiments/README.md). The commands below invoke
that implementation directly. This document retains the ReAct-specific notebook
procedure; existing archives, prompts and configuration remain in this repository.

This directory documents the manual procedure for React CCRS maze runs.
The tooling uses the BDI experiment package shape where the data is comparable,
while documenting React-specific advisory prompt metrics instead of BDI
deterministic option-reordering metrics.

Each batch compares one React baseline agent with one React CCRS agent in the
same scenario.

## Quick Start Checklist

Use this table as the manual experiment loop.

Start an experiment agent only after all setup agents have finished their runs or reached their final positions.

### MASE Scenario V1

| Step | Where | Action | Command or UI action |
| ---: | --- | --- | --- |
| 1 | `\ccrs-react` | Prepare the staging folder | `powershell -ExecutionPolicy Bypass -File ../ccrs-experiments/scripts/react/prepare-current-run.ps1 -RepositoryRoot .` |
| - | ********** | ********************** | ********************** |
| 2 | `\mase` | Start MASE server (configure scenario in .properties) and viewer | `docker compose -f docker-compose.ccrs.yml --profile viewer up --build -d mase-viewer` |
| 3 | `\mase` | Start CCRS scenario services for the run | `docker compose -f docker-compose.ccrs.yml up --build -d ccrs-agent keyholder-agent` |
| 4 | Browser | Open the viewer | `http://localhost:3000` |
| - | ********** | ********************** | ********************** |
| 5 | `test_agent.ipynb` | **BASELINE V1** | `agent_name="react_baseline_mazeV1"` |
| 6 | Browser | Export and reset after the run | `Reset Store` -> `Export logs`; save the NDJSON file into `S:\dev\ma\ccrs-react\experiments\runs\latest`; confirm reset |
| 7 | `\ccrs-react` | Stage the logs | `powershell -ExecutionPolicy Bypass -File ../ccrs-experiments/scripts/react/import-manual-run.ps1 -RepositoryRoot . -BatchId react-baseline-vs-ccrs-v1 -RunId 300-baseline -AgentName react_baseline_mazeV1 -ScenarioId CcrsMazeV1` |
| - | ********** | ********************** | ********************** |
| 8 | `test_agent.ipynb` | **REACT V1** | Re-run step 3. to prepare environment, then run cell with `agent_name="react_ccrs_mazeV1"` |
| 9 | Browser | Export and reset after the run | `Reset Store` -> `Export logs`; save the NDJSON file into `S:\dev\ma\ccrs-react\experiments\runs\latest`; confirm reset |
| 10 | `\ccrs-react` | Stage the logs | `powershell -ExecutionPolicy Bypass -File ../ccrs-experiments/scripts/react/import-manual-run.ps1 -RepositoryRoot . -BatchId react-baseline-vs-ccrs-v1 -RunId 400-ccrs -AgentName react_ccrs_mazeV1 -ScenarioId CcrsMazeV1` |
| - | ********** | ********************** | ********************** |
| 11 | `\ccrs-react` | **GENERATE REPORT** | `powershell -ExecutionPolicy Bypass -File ../ccrs-experiments/scripts/react/write-report.ps1 -RepositoryRoot . -BatchId react-baseline-vs-ccrs-v1` |

### MASE Scenario V2

| Step | Where | Action | Command or UI action |
| ---: | --- | --- | --- |
| 1 | `\ccrs-react` | Prepare the staging folder | `powershell -ExecutionPolicy Bypass -File ../ccrs-experiments/scripts/react/prepare-current-run.ps1 -RepositoryRoot .` |
| - | ********** | ********************** | ********************** |
| 2 | `\mase` | Start MASE server (configure scenario in .properties) and viewer | `docker compose -f docker-compose.ccrs.yml --profile viewer up --build -d mase-viewer` |
| 3 | `\mase` | Start CCRS scenario services for the run | `docker compose -f docker-compose.ccrs.yml up --build -d ccrs-agent keyholder-agent` |
| 4 | Browser | Open the viewer | `http://localhost:3000` |
| - | ********** | ********************** | ********************** |
| 5 | `test_agent.ipynb` | **BASELINE V2** | `agent_name="react_baseline_mazeV2"` |
| 6 | Browser | Export and reset after the run | `Reset Store` -> `Export logs`; save the NDJSON file into `S:\dev\ma\ccrs-react\experiments\runs\latest`; confirm reset |
| 7 | `\ccrs-react` | Stage the logs | `powershell -ExecutionPolicy Bypass -File ../ccrs-experiments/scripts/react/import-manual-run.ps1 -RepositoryRoot . -BatchId react-baseline-vs-ccrs-v2 -RunId 700-baseline -AgentName react_baseline_mazeV2 -ScenarioId CcrsMazeV2` |
| - | ********** | ********************** | ********************** |
| 8 | `test_agent.ipynb` | **REACT V2** | Re-run step 3. to prepare environment, then run cell with `agent_name="react_ccrs_mazeV2"` |
| 9 | Browser | Export and reset after the run | `Reset Store` -> `Export logs`; save the NDJSON file into `S:\dev\ma\ccrs-react\experiments\runs\latest`; confirm reset |
| 10 | `\ccrs-react` | Stage the logs | `powershell -ExecutionPolicy Bypass -File ../ccrs-experiments/scripts/react/import-manual-run.ps1 -RepositoryRoot . -BatchId react-baseline-vs-ccrs-v2 -RunId 800-ccrs -AgentName react_ccrs_mazeV2 -ScenarioId CcrsMazeV2` |
| - | ********** | ********************** | ********************** |
| 11 | `\ccrs-react` | **GENERATE REPORT** | `powershell -ExecutionPolicy Bypass -File ../ccrs-experiments/scripts/react/write-report.ps1 -RepositoryRoot . -BatchId react-baseline-vs-ccrs-v2` |


## Run Package Shape

[scripts/import-manual-run.ps1](../../ccrs-experiments/scripts/react/import-manual-run.ps1) writes each run
under `experiments/runs/<batch-id>/<run-id>/`.

- `run.json`: run metadata, agent name, imported log names, MASE
  capture status, and optional scenario fields.
- `mase-events.jsonl`: normalized MASE viewer export, when present.
- `source-exports/`: original MASE exports and staging metadata.
- `<run>.log`: copied React log.
- `<run>.java.log`: copied Java companion log when present.
- `manifest.json`: batch-level manifest refreshed after every import.

By default, the import script selects the newest `logs/<AgentName>*.log` file
that is not a Java companion log, then copies the same-stem `.java.log` file if
it exists. `-ReactLog` and `-JavaLog` remain available for explicit overrides.
Staged MASE exports are moved out of `latest` unless `-KeepSource` is supplied.

Supply `-ScenarioId CcrsMazeV1` or `-ScenarioId CcrsMazeV2` when importing;
explicit scenario metadata takes precedence over the batch name in the report.

## CSV Artifacts

[scripts/parse-experiment-logs.ps1](../../ccrs-experiments/scripts/react/parse-experiment-logs.ps1) writes
CSV files into `experiments/reports/<batch-id>/`.

- `runs.csv`: one row per imported run with scenario metadata, MASE counts, React
  CCRS event counts, Java evidence counts, and `decision_metric_quality`.
- `agents.csv`: one row per imported experiment agent observed in MASE, with
  movement count and final cell.
- `mase-events.csv`: normalized MASE event rows filtered to the imported
  experiment agent.
- `mase-agent-moved.csv`: evaluated `AGENT_MOVED` rows for the imported agent;
  initial placement on `cells/0` is excluded, and step 1 is the first move out
  of `cells/0`. Later returns to `cells/0` count normally.
- `mase-transactions.csv`: normalized MASE transaction rows filtered to the
  imported experiment agent.
- `move-durations.csv`: one row per successful move window from
  `move-action-correlation.csv`, with move-to-move duration and HTTP
  success/failure call counts.
- `cycle-durations.csv`: React loop-cycle rows. Fresh logs populate these from
  `react.loop.cycle` events emitted from the React state cycle channel; older
  CCRS logs may contain historical structured cycle rows.
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
- `move-duration-comparison.svg`: SVG chart of move-to-move duration by
  movement step, with HTTP success/failure calls stacked on a second y-axis.
- `cycle-duration-comparison.svg`: SVG chart of React loop-cycle duration by
  cycle step.
- `java-library-evidence.csv`: Java companion log evidence, kept separate from
  React adapter decisions.
- `path-analysis-inputs/*.cells.txt`: movement paths grouped by run and MASE
  agent, including `cells/0` as the uncounted path origin when present.
- `summary.json`: parser/report metadata and aggregate artifact counts.
- `summary.md`: first-version Markdown report.

Metric definitions are maintained in [REACT_METRICS.md](../../ccrs-experiments/docs/REACT_METRICS.md).

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
[audit.py](https://github.com/stefanmhsg/ccrs/blob/master/ccrs-langgraph/src/ccrs_langgraph/audit.py). The reportability events added for
advisory-follow metrics are:

- `react.ccrs.prompt_context.visible`: emitted before the LLM call when any
  CCRS context is visible in the prompt.
- `react.ccrs.opportunistic.selection`: emitted after the LLM response for each
  selected tool call.

The parser also reads existing opportunistic, contingency, and
contingency-produced guidance events documented in
[CCRS LangGraph adapter README.md](https://github.com/stefanmhsg/ccrs/blob/master/ccrs-langgraph/README.md).

# React CCRS Experiment Reports

Current import/report code and synthetic tests are maintained in
[ccrs-experiments](../../ccrs-experiments/README.md). The commands below invoke
that implementation directly. This document retains the ReAct-specific notebook
procedure; existing archives, prompts and configuration remain in this repository.

This directory documents the manual procedure for React CCRS maze runs.
The tooling uses the BDI experiment package shape where the data is comparable,
while documenting React-specific advisory prompt metrics instead of BDI
deterministic option-reordering metrics.

Use the [guided ReAct procedure](../../ccrs-experiments/docs/GUIDED_REACT.md)
for registered runs and automatic LangSmith capture. Execute one configuration at
a time. The study targets three baseline and three CCRS executions per scenario,
without individual pair assignments; combined reports remain deferred.
The manual imports below retain their storage BatchId, which is not a repetition.

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
| 11 | `\ccrs-react` | **GENERATE REPORT** | `python ../ccrs-experiments/scripts/experiment.py report-package --architecture react --package experiments/runs/react-baseline-vs-ccrs-v1/300-baseline` |

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
| 11 | `\ccrs-react` | **GENERATE REPORT** | `python ../ccrs-experiments/scripts/experiment.py report-package --architecture react --package experiments/runs/react-baseline-vs-ccrs-v2/700-baseline` |


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

## Individual reports and evidence

Run the report command separately for each imported package. It produces
report/summary.md and report/metrics.json beside that package's raw evidence.
Registered runs use `registry report --run-id <id>` from the experiments repository;
reporting is available for pending, valid and excluded runs.

The shared Python reporter retains mase-agent-moved.csv with initial placement as
the uncounted t0 anchor. It derives navigation intervals from successful MASE
transitions, independent of LLM cycles and action matching. Other outputs include
navigation-intervals.csv, decisions.csv, guidance.csv, strategy-durations.csv,
events.csv and zone-summary.csv. Definitions and coverage limitations are in the
[measurement contract](../../ccrs-experiments/docs/MEASUREMENT_CONTRACT.md) and
[ReAct metrics](../../ccrs-experiments/docs/REACT_METRICS.md).

Preserve the full LangSmith tree: decision-time advertised alternatives, exact
prompt-visible guidance and accepted tool actions support selection measurement.
Raw same-cycle detections alone do not establish what the LLM saw. Prompt-derived
DFS-reference rules remain open; reports do not fabricate deterministic LLM rankings.
The Java companion log provides strategy evaluations that Python traces alone may lack.

[runner.py](../react_agent/runner.py) emits agent.run.finished with timestamp_utc,
reason and exception type for graph return, exception or interruption. A graph
return does not establish maze completion; the reporter uses MASE exit arrival.
Restart the notebook kernel after updating imported code and run its reload cell.

Structured CCRS events come from the external
[LangGraph adapter](../../ccrs/ccrs-langgraph/README.md), including
react.ccrs.prompt_context.visible and react.ccrs.opportunistic.selection. The latter
also records proposals, so accepted navigation choices are reconstructed from the
full trace rather than counted blindly. New adapter/core UTC and invocation-ID
instrumentation requires coordinated library versions; source changes alone do not
update an installed notebook kernel.

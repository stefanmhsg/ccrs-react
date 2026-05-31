# PLAN_EXPERIMENT_REPORTS: Generate BDI-aligned reports for React CCRS experiment runs

This ExecPlan is a living document. The sections `Rules`, `Progress`, `Surprises & Discoveries`, and `Decision Log` must be kept up to date as work proceeds. Work packages must be kept current with their local context, discussion, todos, concrete steps, validation, and outcomes.

No repository-local `PLANS.md` or `.agent/PLANS.md` guide is currently checked in. This document follows the local `PLAN_<SCOPE>.md` convention described in [AGENTS.md](AGENTS.md) and extends the existing React CCRS implementation plan in [PLAN_CCRS_README.md](PLAN_CCRS_README.md).

## Purpose / Big Picture

React CCRS experiment runs should produce the same kind of analysis package that the BDI agents already produce under [ccrs-bdi/experiments](../ccrs-bdi/experiments/). After this work, a user can run a baseline React agent and a CCRS React agent manually, export MASE viewer event logs into a clean staging directory, archive each run into a durable run directory, and generate a Markdown report plus CSV/JSON artifacts that compare outcomes, movement, cycle timing, opportunistic CCRS, contingency CCRS, and MASE-side transactions.

The first target is a manual and auditable workflow rather than a fully automated runner. The experiment loop remains under the user's control: prepare a clean current-run log directory, configure the scenario, run one agent, export MASE events, import the run, repeat for the next agent, and then generate the report.

## Rules

- Rule: Align React experiment artifacts with the BDI experiment output shape unless there is a concrete React-specific reason to differ.
  Reason: The goal is to compare React and BDI reports and reuse the mental model already established by [ccrs-bdi/experiments/README.md](../ccrs-bdi/experiments/README.md).
  Added/Updated: 2026-05-31 / Codex.

- Rule: Keep the experiment procedure manual-first and idempotent.
  Reason: The user runs the agent and exports MASE viewer logs manually; scripts should stage, archive, parse, and report without hiding or mutating the live run.
  Added/Updated: 2026-05-31 / Codex.

- Rule: Treat `ccrs-react/experiments/runs/current-run/` as disposable staging and `ccrs-react/experiments/runs/<batch-id>/<run-id>/` as durable run archives.
  Reason: A clean staging folder makes it clear which logs belong to the just-finished run, while durable run directories support repeated report generation.
  Added/Updated: 2026-05-31 / Codex.

- Rule: Use `S:\anaconda\agent\python.exe` for React-side smoke validation.
  Reason: [AGENTS.md](AGENTS.md) records that this interpreter has the required LangChain, JPype, and RDF dependencies for `ccrs-react`.
  Added/Updated: 2026-05-31 / Codex.

- Rule: Do not require a full LLM or MaSE maze run to validate the report parser.
  Reason: Report-generation logic should be smoke-testable with small fixture logs and copied MASE export samples before costly live runs.
  Added/Updated: 2026-05-31 / Codex.

- Rule: Do not treat Java CCRS library logs as a substitute for adapter-specific experiment events.
  Reason: BDI and React use different CCRS adapters. Java core logs can prove library behavior, but adapter decisions such as option prioritization, prompt injection, escalation, and selected tool calls must come from adapter-specific React events.
  Added/Updated: 2026-05-31 / Codex.

## Now / Next / Later

| NOW | NEXT | LATER |
| --- | --- | --- |
| WP1: Align schemas and event vocabulary | WP4: Add richer CCRS report sections | WP6: Automate more of the live experiment loop |
| WP2: Implement staging and import scripts | WP5: Add smoke fixtures and validation scripts | WP7: Cross-repository comparison reports |
| WP3: Parse React logs and MASE exports |  |  |

## Progress

- [x] (2026-05-31 13:20Z) Created this React experiment-report ExecPlan and aligned its initial workflow with [ccrs-bdi/experiments/README.md](../ccrs-bdi/experiments/README.md).
- [ ] WP1: Inventory BDI report CSV schemas and map each field to React log or MASE export sources.
- [ ] WP2: Add React experiment staging/import/report PowerShell scripts under `ccrs-react/experiments/scripts/`.
- [ ] WP3: Implement a parser that reads React run logs, Java companion logs, and MASE viewer exports into normalized CSVs.
- [ ] WP4: Generate `summary.md`, `summary.json`, CSVs, and path-analysis inputs with the same report layout used by BDI where possible.
- [ ] WP5: Add small smoke fixtures or smoke commands that exercise report generation without a live OpenAI or MaSE run.

## Surprises & Discoveries

- Observation: The BDI report pipeline already has the desired archive and report shape.
  Evidence: [ccrs-bdi/experiments/scripts/import-manual-run.ps1](../ccrs-bdi/experiments/scripts/import-manual-run.ps1) archives staging files into `experiments/runs/<batch-id>/<run-id>/`, and [ccrs-bdi/experiments/scripts/write-report.ps1](../ccrs-bdi/experiments/scripts/write-report.ps1) writes `summary.md`, `summary.json`, CSV files, and path-analysis inputs under `experiments/reports/<batch-id>/`.

- Observation: React logs already contain machine-readable CCRS audit events, but the parser must distinguish React adapter events from Java library events.
  Evidence: [react_agent/ccrs/README.md](react_agent/ccrs/README.md) documents `[REACT-CCRS-EVENT] event=react.ccrs...` in `logs/<run>.log` and Java companion records in `logs/<run>.java.log`.

- Observation: The React CCRS implementation plan already defines smoke checks that can seed report-parser validation.
  Evidence: [PLAN_CCRS_README.md](PLAN_CCRS_README.md) includes local validation commands for graph construction, Java-backed opportunistic scans, Java-backed contingency evaluation, invalid RDF handling, and prompt-path behavior.

- Observation: Existing BDI opportunistic reporting depends on a JaCaMo adapter event that React does not currently produce.
  Evidence: [prioritize.java](../ccrs-bdi/ccrs-jacamo/src/main/java/ccrs/jacamo/jason/opportunistic/prioritize.java) emits `ccrs.opportunistic.prioritize` with fields such as `selected_uri`, `selected_original_index`, `selected_has_ccrs`, `selected_reordered`, `selected_type`, and `selected_utility`. [parse-experiment-logs.ps1](../ccrs-bdi/experiments/scripts/parse-experiment-logs.ps1) maps that event into `decisions.csv`. The current React adapter emits `react.ccrs.opportunistic.detected` for scan results and prompt-context events for injection, but it does not yet emit an equivalent post-LLM decision event that says which option was selected and whether CCRS influenced that selection.

## Decision Log

- Decision: Create the React report plan as [PLAN_EXPERIMENT_REPORTS.md](PLAN_EXPERIMENT_REPORTS.md) in `ccrs-react`.
  Rationale: Report generation is a distinct final implementation effort from the CCRS adapter itself, and a dedicated plan prevents the adapter plan from becoming a catch-all.
  Date/Author: 2026-05-31 / Codex.

- Decision: Mirror the BDI experiment directory model inside `ccrs-react/experiments/`.
  Rationale: Matching `experiments/runs/`, `experiments/reports/`, and `experiments/scripts/` makes React reports easier to compare with BDI reports and keeps generated artifacts out of the agent package.
  Date/Author: 2026-05-31 / Codex.

- Decision: Use a disposable `current-run` staging directory for the manual loop.
  Rationale: The user wants to prepare a clean current-run log directory, run the agent, export MASE event logs there, and then let scripts archive that exact run into a durable run package.
  Date/Author: 2026-05-31 / Codex.

- Decision: React report generation must distinguish Java-library evidence from React-adapter evidence.
  Rationale: Java CCRS logs differ depending on which adapter uses the library and cannot by themselves reproduce adapter-specific BDI report metrics. React reports should parse Java companion logs as library evidence, but metrics such as opportunistic influence, prompt injection, escalation, and selected actions require React adapter events.
  Date/Author: 2026-05-31 / Codex.

## Context and Orientation

The repository for this plan is `ccrs-react`. It contains the React/LangGraph agent, including the baseline graph and the CCRS graph. The current CCRS graph is [react_agent/graph/graph_ccrs.py](react_agent/graph/graph_ccrs.py). Users can run it through [main.py](main.py) or [react_agent/api.py](react_agent/api.py). The active React CCRS adapter documentation is [react_agent/ccrs/README.md](react_agent/ccrs/README.md), and the adapter implementation plan is [PLAN_CCRS_README.md](PLAN_CCRS_README.md).

The reference implementation for experiment reports is in the sibling BDI repository. [ccrs-bdi/experiments/README.md](../ccrs-bdi/experiments/README.md) documents the manual experiment workflow. [ccrs-bdi/experiments/scripts/import-manual-run.ps1](../ccrs-bdi/experiments/scripts/import-manual-run.ps1) imports one staged run. [ccrs-bdi/experiments/scripts/parse-experiment-logs.ps1](../ccrs-bdi/experiments/scripts/parse-experiment-logs.ps1) normalizes logs into CSV files. [ccrs-bdi/experiments/scripts/write-report.ps1](../ccrs-bdi/experiments/scripts/write-report.ps1) refreshes the CSVs and writes `summary.md`.

The React report pipeline should start with the same manual procedure:

1. Prepare a clean staging directory at `ccrs-react/experiments/runs/current-run/`.
2. Set up the MaSE scenario outside this repository.
3. Run one React agent, usually baseline or CCRS.
4. Let React logs be captured under `ccrs-react/logs/`.
5. After the run ends, export MASE viewer event logs and place the export in `ccrs-react/experiments/runs/current-run/`.
6. Run a PowerShell import script that copies or moves the relevant React logs and MASE export into `ccrs-react/experiments/runs/<batch-id>/<run-id>/`.
7. Reset/recreate the scenario, run the second agent, and import that run into the same batch.
8. Run a PowerShell report script that writes `ccrs-react/experiments/reports/<batch-id>/summary.md`.

The term "run package" means one durable directory containing all raw and normalized files for one finished agent run. The term "batch" means a set of run packages that should be compared in one report, for example `react-baseline-vs-ccrs-v1` with `001-baseline` and `002-ccrs` runs.

## Work Packages

### WP1: Align React report schemas with BDI reports

Status: Now

Purpose: Define the React CSV and report schema before writing scripts, so generated reports can be compared with existing BDI reports without ad hoc field names.

Local context: Use [ccrs-bdi/experiments/reports/baseline-vs-ccrs-v2/summary.md](../ccrs-bdi/experiments/reports/baseline-vs-ccrs-v2/summary.md) as an example report. Use [ccrs-bdi/experiments/scripts/parse-experiment-logs.ps1](../ccrs-bdi/experiments/scripts/parse-experiment-logs.ps1) and [ccrs-bdi/experiments/scripts/write-report.ps1](../ccrs-bdi/experiments/scripts/write-report.ps1) as the schema reference. Use [react_agent/ccrs/README.md](react_agent/ccrs/README.md) for React CCRS event names and log file structure.

Discussion: React cannot copy BDI parsing one-to-one because BDI logs are JaCaMo/AgentSpeak logs, while React logs are Python logging records plus optional Java companion logs. The output should nevertheless preserve familiar files where the data exists: `runs.csv`, `agents.csv`, `mase-events.csv`, `mase-agent-moved.csv`, `mase-transactions.csv`, `cycle-durations.csv`, `decisions.csv`, `contingency.csv`, `actions.csv`, `path-analysis-inputs.csv`, `summary.json`, and `summary.md`. If a BDI-specific column has no React source, leave it blank or define a React equivalent explicitly.

The most important known mismatch is opportunistic decision reporting. In BDI, the Java core scan result is not enough for `decisions.csv`; the JaCaMo adapter's [prioritize.java](../ccrs-bdi/ccrs-jacamo/src/main/java/ccrs/jacamo/jason/opportunistic/prioritize.java) internal action emits `ccrs.opportunistic.prioritize`, which records how CCRS annotations changed the selected option. React currently uses advisory prompt injection, so there is no deterministic prioritize internal action and no direct `selected_reordered` equivalent. React report v1 must therefore either mark those BDI decision fields as unavailable for React or add a React adapter event that records the prompt-visible CCRS context, the LLM-selected tool/action target, and the matching CCRS entry if one exists.

Todos:

- [ ] List all CSV files produced by the BDI report pipeline and decide which are required for React v1.
- [ ] Map BDI run metadata fields to React run metadata fields, including `graph_name`, `agent_name`, `run_mode`, `log_level`, and whether `enable_contingency_escalation_tool` was enabled.
- [ ] Map React `[REACT-CCRS-EVENT]` names into `decisions.csv`, `contingency.csv`, and cycle attribution fields.
- [ ] Identify every BDI metric that depends on JaCaMo adapter events rather than Java CCRS core events, starting with `ccrs.opportunistic.prioritize`.
- [ ] Decide the React equivalent for BDI `ccrs.opportunistic.prioritize`: unavailable in v1, inferred from prompt context plus selected tool call, or emitted as a new React adapter event.
- [ ] Decide whether React cycle durations come from existing `cycle` timestamps, a new structured log marker, or both.
- [ ] Define how Java companion logs contribute to report evidence without duplicating React adapter event counts.

Concrete steps: Start from `S:\dev\ma\ccrs-react` and inspect the BDI outputs and React event vocabulary:

    rg -n "REACT-CCRS-EVENT|react.ccrs|Cycle:|LLM_NODE_CCRS_V2|TOOL_NODE" react_agent logs
    rg -n "Export-Csv|Add-Contingency|Add-CycleMarker|Add-MaseEvent" ..\ccrs-bdi\experiments\scripts

Record the final schema mapping in this work package before implementing WP2 and WP3.

Validation and acceptance: WP1 is accepted when the plan or a new `ccrs-react/experiments/README.md` section states which BDI report artifacts React will generate in v1, where each field comes from, and which fields are intentionally blank or React-specific.

Outcome and notes: Not started.

### WP2: Add manual staging and import scripts

Status: Now

Purpose: Give the user a repeatable PowerShell workflow for turning a just-finished React run plus exported MASE events into a durable run package.

Local context: The BDI import script in [ccrs-bdi/experiments/scripts/import-manual-run.ps1](../ccrs-bdi/experiments/scripts/import-manual-run.ps1) is the closest reference. React logs are written under `ccrs-react/logs/` by [react_agent/utils/logging_config.py](react_agent/utils/logging_config.py). Java companion logs use the same run name with `.java.log`, as documented in [react_agent/ccrs/README.md](react_agent/ccrs/README.md).

Discussion: The import script should not run the agent. The user runs the agent manually from [main.py](main.py), [test_agent.ipynb](test_agent.ipynb), or another launcher. The script should package the result after the run ends. It should accept explicit log paths because multiple React logs can exist in `logs/`, and automatic selection by timestamp can be wrong after notebook experiments.

Todos:

- [ ] Create `ccrs-react/experiments/scripts/prepare-current-run.ps1` to create or clean `experiments/runs/current-run/`.
- [ ] Create `ccrs-react/experiments/scripts/import-manual-run.ps1` aligned with the BDI script but with React parameters such as `-AgentName`, `-GraphName`, `-RunMode`, `-ReactLog`, `-JavaLog`, and `-EnableContingencyEscalationTool`.
- [ ] Normalize MASE viewer NDJSON/JSONL exports into `mase-events.jsonl` in each run package.
- [ ] Preserve original exports under `source-exports/`.
- [ ] Write `run.json` with enough metadata for report generation and audit.
- [ ] Update or create a batch-level `manifest.json` after each import.

Concrete steps: Implement scripts under `ccrs-react/experiments/scripts/`. The intended manual commands should look like:

    powershell -ExecutionPolicy Bypass -File experiments\scripts\prepare-current-run.ps1

    S:\anaconda\agent\python.exe main.py --graph-name graph --agent-name react_baseline_1 --log-level INFO

    powershell -ExecutionPolicy Bypass -File experiments\scripts\import-manual-run.ps1 `
      -BatchId react-baseline-vs-ccrs-v1 `
      -RunId 001-baseline `
      -AgentName react_baseline_1 `
      -GraphName graph `
      -ReactLog logs\react_baseline_1_YYYYMMDD_HHMMSS.log

    powershell -ExecutionPolicy Bypass -File experiments\scripts\prepare-current-run.ps1

    S:\anaconda\agent\python.exe main.py --graph-name graph_ccrs --enable-contingency-escalation-tool --agent-name react_ccrs_1 --log-level INFO

    powershell -ExecutionPolicy Bypass -File experiments\scripts\import-manual-run.ps1 `
      -BatchId react-baseline-vs-ccrs-v1 `
      -RunId 002-ccrs `
      -AgentName react_ccrs_1 `
      -GraphName graph_ccrs `
      -EnableContingencyEscalationTool `
      -ReactLog logs\react_ccrs_1_YYYYMMDD_HHMMSS.log `
      -JavaLog logs\react_ccrs_1_YYYYMMDD_HHMMSS.java.log

Validation and acceptance: Running the import command with a small staged MASE export and existing React log should create `experiments/runs/<batch-id>/<run-id>/run.json`, copy or move React logs into the run directory, write `mase-events.jsonl` when exports exist, preserve original exports under `source-exports/`, and refresh `manifest.json`.

Outcome and notes: Not started.

### WP3: Parse React logs and MASE exports

Status: Now

Purpose: Convert archived run packages into normalized CSV files that the report writer can use.

Local context: BDI parsing lives in [ccrs-bdi/experiments/scripts/parse-experiment-logs.ps1](../ccrs-bdi/experiments/scripts/parse-experiment-logs.ps1). React adapter audit events are emitted by [react_agent/ccrs/audit.py](react_agent/ccrs/audit.py). Event names are documented in [react_agent/ccrs/README.md](react_agent/ccrs/README.md). MASE viewer exports should be parsed with the same general logic used by the BDI parser: keep events for the experiment agent and produce movement, transaction, and path-analysis rows.

Discussion: The React parser needs a stable key-value parser for `[REACT-CCRS-EVENT]` records and may also parse `[CCRS-EVENT]` records in `.java.log` as Java-side evidence. React logs include Python logger names and timestamps before the CCRS prefix; the parser should search for the prefix within the line rather than assume it starts at column zero. Existing prompt context and notebook console output may be useful for manual inspection, but report generation should depend on file logs whenever possible.

Adapter-level event differences must be handled explicitly. Java companion logs can show that `VocabularyMatcher` or `ContingencyCcrs` ran, but they cannot reconstruct React-specific graph effects such as prompt injection, LLM self-escalation, skipped tool-node routing, or which tool call the LLM selected after seeing CCRS context. BDI's `decisions.csv` is populated partly from `ccrs.opportunistic.prioritize`; React needs either a new adapter event with comparable semantics or report columns that clearly state `not_available_for_react_adapter`.

Todos:

- [ ] Create `ccrs-react/experiments/scripts/parse-experiment-logs.ps1`.
- [ ] Parse `[REACT-CCRS-EVENT] event=react.ccrs.opportunistic.*` into opportunistic counts and optional detail rows.
- [ ] Parse `[REACT-CCRS-EVENT] event=react.ccrs.contingency.*` into `contingency.csv`.
- [ ] Parse `react.ccrs.opportunistic_guidance_by_contingency_ccrs.*` into guidance match counts.
- [ ] Do not infer BDI `selected_reordered` or overruled-decision metrics from Java scan logs alone.
- [ ] If React decision influence metrics are required, add or consume a React adapter event that correlates latest prompt-visible CCRS entries with the subsequent LLM tool call target.
- [ ] Parse Java companion `.java.log` files into a separate evidence table or summary fields without double-counting adapter events.
- [ ] Parse MASE `AGENT_MOVED` and transaction events into `mase-events.csv`, `mase-agent-moved.csv`, `mase-transactions.csv`, `agents.csv`, and path-analysis inputs.
- [ ] Derive `cycle-durations.csv` from React cycle timestamps or add a required structured cycle marker if current logs are insufficient.
- [ ] Write per-run CSVs into the run package when useful and batch-level CSVs into `experiments/reports/<batch-id>/`.

Concrete steps: Implement parser functions for run metadata, key-value records, MASE JSONL records, and output CSV writing. Reuse naming and field shapes from the BDI parser where possible, but keep React-specific fields such as `graph_name`, `react_event`, `tool_call_id`, `cycle`, `cycle_timestamp`, `strategy_id`, `top_action`, and `stop`.

Validation and acceptance: A parser smoke should be able to read one small run package containing a React log with at least one opportunistic event, one contingency event, one Java companion log line, and a tiny MASE event export. It should write non-empty `runs.csv`, `mase-events.csv`, and the relevant CCRS CSVs without requiring a live LLM or MaSE server.

Outcome and notes: Not started.

### WP4: Generate BDI-aligned summary reports

Status: Next

Purpose: Produce the human-readable report and machine-readable summary package for one React experiment batch.

Local context: The BDI report writer in [ccrs-bdi/experiments/scripts/write-report.ps1](../ccrs-bdi/experiments/scripts/write-report.ps1) generates the report sections that users already know: core metrics, move optimality, cycle duration summary, chart, decision breakdown, contingency details, generated artifacts, and path-analysis inputs.

Discussion: React v1 should prefer the same report sections even if some tables have fewer rows. The report should make React-specific behavior visible: whether the CCRS graph was used, whether the escalation tool was enabled, how many opportunistic annotations were detected, how many contingency escalations occurred, how often contingency suggestions stopped the graph, and whether Java companion logs were captured.

Todos:

- [ ] Create `ccrs-react/experiments/scripts/write-report.ps1`.
- [ ] Have it call `parse-experiment-logs.ps1` before writing the report.
- [ ] Write `summary.md` and `summary.json`.
- [ ] Include the generated CSV artifact list.
- [ ] Generate path-analysis cell sequence files from MASE movement rows.
- [ ] Add a cycle-duration chart if React cycle rows are available.

Concrete steps: Keep the command shape close to BDI:

    powershell -ExecutionPolicy Bypass -File experiments\scripts\write-report.ps1 -BatchId react-baseline-vs-ccrs-v1

Expected outputs should include:

    experiments\reports\react-baseline-vs-ccrs-v1\summary.md
    experiments\reports\react-baseline-vs-ccrs-v1\summary.json
    experiments\reports\react-baseline-vs-ccrs-v1\runs.csv
    experiments\reports\react-baseline-vs-ccrs-v1\mase-events.csv
    experiments\reports\react-baseline-vs-ccrs-v1\mase-agent-moved.csv
    experiments\reports\react-baseline-vs-ccrs-v1\mase-transactions.csv
    experiments\reports\react-baseline-vs-ccrs-v1\contingency.csv

Validation and acceptance: The report command should be idempotent. Running it twice for the same batch should refresh generated CSVs and Markdown without modifying archived raw logs. Opening `summary.md` should show both runs, final cell or outcome, movement counts, CCRS event counts for the CCRS run, and links or filenames for generated CSV artifacts.

Outcome and notes: Not started.

### WP5: Add smoke fixtures and validation commands

Status: Next

Purpose: Let report-generation work be validated without spending LLM tokens or running the full maze scenario.

Local context: [PLAN_CCRS_README.md](PLAN_CCRS_README.md) already defines short Python smoke commands for graph construction and Java-backed CCRS evaluation. This plan needs report-specific smoke data: tiny React log snippets, a tiny Java companion log snippet, and a tiny MASE JSONL export.

Discussion: Smoke fixtures should be intentionally small and human-readable. They should not be confused with real experiment evidence. The scripts should accept fixture directories through parameters so they can be run from CI-like contexts later.

Todos:

- [ ] Add a small fixture run package under a clearly named non-report directory, for example `experiments/fixtures/smoke-run/`.
- [ ] Include one baseline-like run fixture and one CCRS-like run fixture if needed for comparison tables.
- [ ] Add a smoke command in [README.md](README.md) or a new `ccrs-react/experiments/README.md`.
- [ ] Validate `parse-experiment-logs.ps1` and `write-report.ps1` against the fixture batch.

Concrete steps: A future implementation should be able to run:

    powershell -ExecutionPolicy Bypass -File experiments\scripts\write-report.ps1 `
      -RunRoot experiments\fixtures\smoke-run `
      -OutputDir experiments\reports\smoke-report

Validation and acceptance: The smoke report should generate a non-empty `summary.md` and the expected CSV files from fixture logs alone. The report should not require `OPENAI_API_KEY`, a running MaSE server, or a live notebook.

Outcome and notes: Not started.

### WP6: Automate more of the live experiment loop

Status: Later

Purpose: Reduce manual steps only after the manual workflow is reliable and auditable.

Local context: The user currently wants to run the agent and export MASE logs manually. Any further automation should preserve that control unless explicitly requested.

Discussion: Later automation could select the latest React log by run name, copy Java companion logs automatically, validate that MASE exports include the configured agent, or start/stop scenario services. These are useful but should not block the first reporting workflow.

Todos:

- [ ] Decide whether latest-log selection is safe enough to add.
- [ ] Consider a `new-run.ps1` helper that stages logs after a run name is provided.
- [ ] Consider optional MaSE Docker orchestration only after user approval.

Concrete steps: Not defined yet.

Validation and acceptance: Later automation is accepted only if the manual script path remains available and clear.

Outcome and notes: Not started.

### WP7: Cross-repository comparison reports

Status: Later

Purpose: Compare React and BDI experiment results in one combined report after both pipelines produce compatible artifacts.

Local context: React reports will live under `ccrs-react/experiments/reports/`; BDI reports already live under [ccrs-bdi/experiments/reports/](../ccrs-bdi/experiments/reports/).

Discussion: This is not required for the first React report generator. It becomes valuable once React and BDI have matching batch scenarios and run metadata.

Todos:

- [ ] Decide whether cross-repository comparison belongs in `ccrs-react`, `ccrs-bdi`, or a separate top-level experiment tool.
- [ ] Define a common minimal schema shared by both pipelines.
- [ ] Generate a combined summary for BDI baseline, BDI CCRS, React baseline, and React CCRS runs.

Concrete steps: Not defined yet.

Validation and acceptance: A combined report should consume existing generated report directories without reparsing raw logs.

Outcome and notes: Not started.

## Validation and Acceptance

The plan is complete when `ccrs-react` can generate a report for a manually collected baseline-vs-CCRS React batch. A successful run should look like this from `S:\dev\ma\ccrs-react`:

    powershell -ExecutionPolicy Bypass -File experiments\scripts\prepare-current-run.ps1
    S:\anaconda\agent\python.exe main.py --graph-name graph --agent-name react_baseline_1 --log-level INFO
    # User exports MASE viewer logs into experiments\runs\current-run\
    powershell -ExecutionPolicy Bypass -File experiments\scripts\import-manual-run.ps1 -BatchId react-baseline-vs-ccrs-v1 -RunId 001-baseline -AgentName react_baseline_1 -GraphName graph -ReactLog logs\<baseline-log>.log

    powershell -ExecutionPolicy Bypass -File experiments\scripts\prepare-current-run.ps1
    S:\anaconda\agent\python.exe main.py --graph-name graph_ccrs --enable-contingency-escalation-tool --agent-name react_ccrs_1 --log-level INFO
    # User exports MASE viewer logs into experiments\runs\current-run\
    powershell -ExecutionPolicy Bypass -File experiments\scripts\import-manual-run.ps1 -BatchId react-baseline-vs-ccrs-v1 -RunId 002-ccrs -AgentName react_ccrs_1 -GraphName graph_ccrs -EnableContingencyEscalationTool -ReactLog logs\<ccrs-log>.log -JavaLog logs\<ccrs-log>.java.log

    powershell -ExecutionPolicy Bypass -File experiments\scripts\write-report.ps1 -BatchId react-baseline-vs-ccrs-v1

The expected observable result is `experiments/reports/react-baseline-vs-ccrs-v1/summary.md` plus CSV and JSON artifacts. The report should identify both runs, use MASE exports for movement and transaction evidence, use React logs for CCRS lifecycle evidence, and preserve Java companion logs as Java-library evidence.

Smoke acceptance does not require a live run. A fixture or copied small run package should be enough to prove that import, parse, and report scripts produce the expected output files.

## Idempotence and Recovery

`prepare-current-run.ps1` should clean only `experiments/runs/current-run/`. It must not delete durable run packages, generated reports, or raw logs under `logs/`.

`import-manual-run.ps1` should create a unique run directory if the requested run id already exists, or fail with a clear message unless an explicit overwrite option is introduced later. It should preserve original MASE exports under `source-exports/` and copy or move source files according to an explicit `-KeepSource` switch, following the BDI script's behavior.

`parse-experiment-logs.ps1` and `write-report.ps1` should be safe to rerun. They may overwrite generated CSV, JSON, SVG, and Markdown files under `experiments/reports/<batch-id>/`, but they must not modify archived raw logs in `experiments/runs/<batch-id>/<run-id>/`.

If a run package is incomplete, scripts should fail with actionable messages. For example, a missing React log should name the expected path and suggest rerunning `import-manual-run.ps1` with `-ReactLog`. A missing MASE export should still allow a React-log-only report, but movement and transaction tables should be empty and marked as missing MASE evidence.

## Artifacts and Notes

BDI report artifacts to mirror where possible:

- `runs.csv`: one row per imported run with outcome and aggregate metrics.
- `agents.csv`: one row per observed MASE agent per run.
- `mase-events.csv`: filtered MASE event records.
- `mase-agent-moved.csv`: normalized MASE movement events.
- `mase-transactions.csv`: normalized MASE transaction events.
- `cycle-durations.csv`: one row per agent cycle marker or derived cycle interval.
- `decisions.csv`: one row per parsed decision or prompt-relevant CCRS selection event when available.
- `contingency.csv`: one row per contingency CCRS evaluation, strategy result, or no-help result.
- `actions.csv`: parsed agent tool/action attempts when recoverable from logs.
- `path-analysis-inputs/*.cells.txt`: copy-paste cell paths for MASE viewer path analysis.
- `summary.json`: parser metadata.
- `summary.md`: human-readable report.

Important React log sources:

    logs/<run>.log
    logs/<run>.java.log
    [REACT-CCRS-EVENT] event=react.ccrs.opportunistic.evaluate ...
    [REACT-CCRS-EVENT] event=react.ccrs.opportunistic.detected ...
    [REACT-CCRS-EVENT] event=react.ccrs.contingency.escalation.activated ...
    [REACT-CCRS-EVENT] event=react.ccrs.contingency.evaluate ...
    [REACT-CCRS-EVENT] event=react.ccrs.contingency.returned ...
    [JAVA-CCRS] ...

The parser should read prefixes inside full log lines because Python logging adds timestamps, levels, and logger names before the structured event marker.

Important BDI-only source to account for when aligning schemas:

    [CCRS-EVENT] event=ccrs.opportunistic.prioritize selected_uri=... selected_reordered=...

That event is emitted by the JaCaMo adapter, not by the shared Java opportunistic matcher. React report generation must not assume it exists. If React needs comparable opportunistic influence metrics, the React adapter should emit its own event after the LLM chooses a tool call, using React naming such as `react.ccrs.opportunistic.selection` or another name chosen during WP1.

## Interfaces and Dependencies

The first implementation should add these files:

- `experiments/README.md`: React experiment workflow and command examples.
- `experiments/scripts/prepare-current-run.ps1`: creates or cleans the disposable staging directory.
- `experiments/scripts/import-manual-run.ps1`: archives one finished run into `experiments/runs/<batch-id>/<run-id>/`.
- `experiments/scripts/parse-experiment-logs.ps1`: parses archived runs into normalized CSV files.
- `experiments/scripts/write-report.ps1`: refreshes parsed CSV files and writes `summary.md`.

The scripts should depend only on PowerShell and files already produced by `ccrs-react`, MaSE viewer exports, and the local filesystem. They should not require Python for the first report pipeline unless a later work package proves Python is a better fit for parsing or chart generation.

If Python is introduced later for parsing, it should use `S:\anaconda\agent\python.exe` during local validation, and the PowerShell report command should remain the user-facing entry point.

Revision note 2026-05-31 / Codex: Created the initial React experiment-report plan from the user's requested workflow and aligned it with the BDI experiment scripts and current React CCRS logging architecture.

Revision note 2026-05-31 / Codex: Added the adapter-specific logging mismatch discovered by comparing BDI `ccrs.opportunistic.prioritize` reporting with current React CCRS logs. The plan now treats Java companion logs as library evidence and requires React adapter events or explicit unavailable fields for adapter-level decision metrics.

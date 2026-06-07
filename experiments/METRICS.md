# React Experiment Metrics

This document defines the metrics currently reported by
[scripts/write-report.ps1](scripts/write-report.ps1). The first report version
is intentionally small: it includes only values with clear sources in archived
run packages and generated CSV artifacts.

## Source Rules

Reports are generated from archived run packages under `experiments/runs/<batch-id>/`.
They do not read notebook output or live console text.

- React adapter evidence comes from `[REACT-CCRS-EVENT]` records in the copied
  React log.
- Java library evidence comes from the copied `.java.log` companion file and is
  kept separate from React adapter decision evidence.
- MASE evidence comes from normalized `mase-events.jsonl` files imported from
  MASE viewer exports.
- Human-readable prompt dumps are useful for manual inspection but are not a
  required parser source.

## Core Metrics

### Run

The imported run id from `run.json`, usually values such as `001-baseline` or
`002-ccrs`.

Source: `runs.csv` column `run_id`.

### Agent

The configured React agent name supplied to
[scripts/import-manual-run.ps1](scripts/import-manual-run.ps1) through
`-AgentName`.

Source: `runs.csv` column `agent_name`.

### Graph

The React graph name supplied during import, for example `graph` or
`graph_ccrs`.

Source: `runs.csv` column `graph_name`.

### Reached Exit

Whether the final tracked MASE cell is the configured exit cell. If `run.json`
contains `exitCell`, the report compares the tracked final cell to that value.
If no exit cell was supplied, the report uses the same scenario metadata as the
BDI writer: `CcrsMazeV1` and `CcrsMazeV2` both use `cells/999`.

Sources: `runs.csv` column `exit_cell`, batch-name scenario metadata, and
`agents.csv` column `final_cell`.

### Total Duration Ms

The sum of derived agent cycle durations for the run. The first observed cycle
has no prior timestamp and does not contribute a duration.

Source: `cycle-durations.csv` column `duration_ms`.

### Total Moves

The number of normalized `AGENT_MOVED` events for the imported experiment agent.
Multi-agent MASE exports are filtered to `run.json` `agentName` / `agentNames`
before report CSV rows are written, so scenario infrastructure agents and other
concurrent experiment agents do not contribute to this metric.

Source: `runs.csv` column `mase_move_count`, derived from filtered
`mase-agent-moved.csv`.

### Average Agent Cycle Duration

The average duration between consecutive React CCRS cycle timestamps observed in
structured React CCRS events. The first observed cycle has no prior timestamp and
does not contribute a duration.

Source: `cycle-durations.csv` column `duration_ms`.

### Final Cell

The final MASE cell for the configured React agent when a matching MASE agent row
exists. The first report version matches either the exact `agent_name` or a MASE
agent URI ending in that name. If no unambiguous row exists, the summary shows
`-`.

Source: `agents.csv` column `final_cell`.

## Move Optimality

Move optimality compares imported actual moves to scenario metadata supplied at
import time.

### Optimal Moves

The scenario-specific optimal move count supplied through
`scripts/import-manual-run.ps1 -OptimalMoves`. If that metadata is blank, the
report falls back to the same scenario metadata as the BDI writer:
`CcrsMazeV1=138` and `CcrsMazeV2=116`.

Source: `runs.csv` column `optimal_moves` or batch-name scenario metadata.

### Actual Moves

The filtered move count for the imported experiment agent.

Source: `runs.csv` column `mase_move_count`.

### Delta From Optimal

`Actual moves - Optimal moves`, but only when the run reached the configured
exit. The report shows `-` when `optimal_moves` is not available or when the
run did not reach the exit.

Sources: `runs.csv` columns `optimal_moves` and `mase_move_count`.

## Cycle Duration Summary

Cycle duration summaries are batch-level aggregates.

- `Baseline avg ms`: average `duration_ms` for non-CCRS runs.
- `CCRS avg ms`: average `duration_ms` for CCRS runs.
- `CCRS opp N avg ms`: average `duration_ms` for CCRS cycles with exactly `N`
  prompt-visible opportunistic CCRS entries, excluding cycles where contingency
  CCRS was activated. Columns are generated from `0` through the maximum
  observed prompt-visible opportunistic count.
- `CCRS cont invocation N avg ms`: average duration for the Nth ordered
  contingency activation cycle across CCRS runs. Columns are generated from `1`
  through the maximum observed invocation count.

Sources: `cycle-durations.csv` columns `duration_ms` and
`opportunistic_prompt_visible_count`, plus `contingency.csv` rows where
`react_event=react.ccrs.contingency.escalation.activated`.

## React CCRS Evidence Artifacts

The summary no longer renders a separate React CCRS Evidence section, but these
artifact counts remain available in generated CSV/JSON files.

### React Events

Count of structured `[REACT-CCRS-EVENT]` records found in the React log.

Source: `runs.csv` column `react_event_count`.

### Prompt-Visible Events

Count of `react.ccrs.prompt_context.visible` records. This event is emitted when
opportunistic CCRS, pending contingency CCRS, or contingency-produced guidance is
visible in the prompt.

Source: `runs.csv` column `prompt_visible_event_count`.

### Selections

Count of `react.ccrs.opportunistic.selection` records. These rows connect an LLM
tool selection to the prompt-visible CCRS context through `prompt_context_id`.

Source: `runs.csv` column `selection_event_count` and `decisions.csv`.

### Opportunistic Detections

Count of `react.ccrs.opportunistic.detected` records emitted by the React
adapter when Java opportunistic CCRS scanning returned an annotation.

Source: `runs.csv` column `opportunistic_detected_count` and
`opportunistic.csv`.

### Contingency Rows

Count of React contingency CCRS events and contingency-produced opportunistic
guidance events normalized into `contingency.csv`.

Source: `runs.csv` column `contingency_event_count` and `contingency.csv`.

### Java Evidence Rows

Count of Java companion log lines preserved as Java library evidence. These rows
show Java-side CCRS activity but do not populate React advisory decision metrics.

Source: `runs.csv` column `java_library_evidence_count` and
`java-library-evidence.csv`.

## Advisory-Follow Metrics

React does not have BDI-style deterministic option reordering. React CCRS
injects advisory prompt context and then records the LLM-selected tool call.

When fresh logs contain `react.ccrs.opportunistic.selection`, the report can
count:

- selections with 0, 1, 2, ... prompt-visible opportunistic CCRS entries,
  continuing dynamically up to the maximum observed count;
- for each non-zero count, selections that chose the rank 1 opportunistic CCRS
  target, where rank 1 is the highest utility target;
- for counts of 2 or more, selections that chose rank 2, rank 3, and so on up
  to the maximum observed rank;
- for each non-zero count, selections that chose none of the opportunistic CCRS
  targets detected for that cycle;
- selections where contingency-produced guidance was visible;
- selections that exactly followed the top contingency-produced target;
- selections that followed the top target from either channel.

Sources: `decisions.csv` columns `opportunistic_count`,
`contingency_guidance_count`, `selected_uri`, `followed_top_opportunistic`,
`followed_top_contingency_guidance`, and `followed_any_top_guidance`, joined to
`opportunistic.csv` rows where `react_event=react.ccrs.opportunistic.detected`.

The opportunistic ranking is inferred per run and cycle by sorting detected
opportunistic CCRS rows by descending numeric `utility`, then by log line as a
stable tie-breaker. A selected URI is counted under the first rank whose
detected `target` exactly matches it. If a non-zero `opportunistic_count`
selection matches no ranked opportunistic target for the same cycle, it is
counted as `selected_none_count`. If the selection reports a non-zero
`opportunistic_count` but no detected target rows are available for that cycle,
it is counted as `rank_unavailable_count` rather than as a non-CCRS selection.

The machine-readable aggregate is `advisory-follow.csv`. Its dynamic rank
columns are named `selected_rank_1_count`, `selected_rank_2_count`, and so on up
to the maximum `opportunistic_count` observed in the report input.

Historical logs that predate `react.ccrs.opportunistic.selection` remain valid
for MASE, cycle, opportunistic, contingency, action, and Java evidence metrics.
Their run rows are marked `decision_metric_quality=missing_selection_event`.

## Not Yet Reported

The following metrics are planned but intentionally excluded from the first
summary version:

- advisory-follow aggregates grouped by `contingency_guidance_count`;
- advisory-follow aggregates grouped by the pair
  `(opportunistic_count, contingency_guidance_count)`;
- zone-level movement summaries;
- cycle duration charts;

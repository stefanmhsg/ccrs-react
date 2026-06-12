# React Experiment Summary: react-baseline-vs-ccrs-v1

Generated: 2026-06-12 14:55:13 +02:00

Run root: `S:\dev\ma\ccrs-react\experiments\runs\react-baseline-vs-ccrs-v1`

Metric definitions: [METRICS.md](../../METRICS.md)

## Core Metrics

| Run | Agent | Graph | Mode | Reached exit | Total duration ms | Total moves | Avg move duration | Final cell |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `001-baseline` | react_baseline_v1_01 | `graph` | notebook | no | 663528 | 65 | 10367.62 | `http://127.0.1.1:8080/cells/12/11` |
| `002-ccrs` | react_ccrs_mazeV1_04 | `graph_ccrs` | notebook | no | 515880 | 37 | 14330 | `http://127.0.1.1:8080/cells/12/5` |

## Move Optimality

| Run | Agent | Optimal moves | Actual moves | Delta from optimal |
| --- | --- | --- | --- | --- |
| `001-baseline` | react_baseline_v1_01 | 138 | 65 | - |
| `002-ccrs` | react_ccrs_mazeV1_04 | 138 | 37 | - |

## Move Duration Summary

| Baseline move avg ms | CCRS move avg ms |
| --- | --- |
| 10367.62 | 14330 |

Move averages use move-durations.csv, derived from move-action-correlation.csv. HTTP calls use the same move windows and are plotted separately.

## Move Duration Chart

![Move duration by step](move-duration-comparison.svg)

X-axis is movement step number; y-axis is log-scaled move duration with ticks at 1000, 2000, 4000, 8000, 16000, 32000, 64000, and 80000 ms.

## HTTP Calls Chart

![HTTP calls by move window](http-calls-by-move.svg)

X-axis is movement step number; y-axis is linear HTTP calls from 0 to 35 in 2-call steps, stacked by success and failure per agent.

## Cycle Duration Summary

| Baseline cycle avg ms | CCRS cycle avg ms | CCRS opp 0 avg ms | CCRS opp 1 avg ms | CCRS cont invocation 1 avg ms | CCRS cont invocation 2 avg ms | CCRS cont invocation 3 avg ms | CCRS cont invocation 4 avg ms |
| --- | --- | --- | --- | --- | --- | --- | --- |
| - | 2867.21 | 2969.11 | 1852.14 | 7834 | 3017 | 2641 | 2990 |

Cycle averages use `cycle-durations.csv`. Fresh runs populate this from `react.loop.cycle` events emitted from the React state cycle channel; historical CCRS-only rows may fall back to older structured CCRS cycle events. Opportunistic CCRS cycle averages exclude cycles where contingency CCRS was activated.

## Cycle Duration Chart

![Cycle duration by step](cycle-duration-comparison.svg)

X-axis is React loop-cycle step number; y-axis is linear cycle duration in milliseconds.

## Advisory-Follow Evidence

| Run | Opp CCRS present | Selections | Selected rank 1 (highest) | Selected none | Rank unavailable |
| --- | --- | --- | --- | --- | --- |
| `002-ccrs` | 0 | 164 | - | - | - |
| `002-ccrs` | 1 | 21 | 19 | 2 | 0 |

Ranks are inferred by joining each selection to `react.ccrs.opportunistic.detected` rows in the same run and cycle, ordered by descending utility. `Selected none` means the selected URI matched none of those ranked opportunistic targets.

## Contingency CCRS Details

### Invocation 1: `002-ccrs`

| Strategy | Result | Action | Target | Confidence | Eval ms | Opportunistic guidance | No-help reason | Rationale |
| --- | --- | --- | --- | ---: | ---: | --- | --- | --- |
| `prediction_llm` | suggestion | post | `http://127.0.1.1:8080/cells/11/9` | 0.95 | 12211 | False | - | LLM suggests: post to http://127.0.1.1:8080/cells/11/9. Reasoning: Direct GET of the adjacent east cell is denied because movement requires first POSTing an entersFrom triple to the destination cell, as shown by prior successful moves.; situation=UNCERTAINTY; trigger=llm_self_escalation; failed_action=http_get |
| `retry` | none | - | - | - | 1 | False | - | situation=UNCERTAINTY; trigger=llm_self_escalation; failed_action=http_get |
| `backtrack` | none | - | - | - | 1 | False | - | situation=UNCERTAINTY; trigger=llm_self_escalation; failed_action=http_get |
| `consultation` | none | - | - | - | 11 | False | - | situation=UNCERTAINTY; trigger=llm_self_escalation; failed_action=http_get |

### Invocation 2: `002-ccrs`

| Strategy | Result | Action | Target | Confidence | Eval ms | Opportunistic guidance | No-help reason | Rationale |
| --- | --- | --- | --- | ---: | ---: | --- | --- | --- |
| `retry` | none | - | - | - | 0 | False | - | situation=FAILURE; trigger=consecutive_http_api_errors; failed_action=http_post |
| `backtrack` | none | - | - | - | 0 | False | - | situation=FAILURE; trigger=consecutive_http_api_errors; failed_action=http_post |
| `consultation` | none | - | - | - | 3 | False | - | situation=FAILURE; trigger=consecutive_http_api_errors; failed_action=http_post |
| `prediction_llm` | none | - | - | - | 0 | False | - | situation=FAILURE; trigger=consecutive_http_api_errors; failed_action=http_post |
| `stop` | none | - | - | - | 1 | False | - | situation=FAILURE; trigger=consecutive_http_api_errors; failed_action=http_post |

### Invocation 3: `002-ccrs`

| Strategy | Result | Action | Target | Confidence | Eval ms | Opportunistic guidance | No-help reason | Rationale |
| --- | --- | --- | --- | ---: | ---: | --- | --- | --- |
| `prediction_llm` | suggestion | post | `http://127.0.1.1:8080/cells/11/11` | 0.95 | 10717 | False | - | LLM suggests: post to http://127.0.1.1:8080/cells/11/11. Reasoning: The current cell 10/11 is a dead end with only a south link to 11/11, and prior successful moves show that navigation requires POSTing an entersFrom triple to the destination using the current cell...; situation=UNCERTAINTY; trigger=llm_self_escalation |
| `retry` | none | - | - | - | 0 | False | - | situation=UNCERTAINTY; trigger=llm_self_escalation |
| `backtrack` | none | - | - | - | 0 | False | - | situation=UNCERTAINTY; trigger=llm_self_escalation |
| `consultation` | none | - | - | - | 3 | False | - | situation=UNCERTAINTY; trigger=llm_self_escalation |

### Invocation 4: `002-ccrs`

| Strategy | Result | Action | Target | Confidence | Eval ms | Opportunistic guidance | No-help reason | Rationale |
| --- | --- | --- | --- | ---: | ---: | --- | --- | --- |
| `stop` | suggestion | stop | - | 1 | 0 | False | - | All 2 recovery strategies exhausted. Trigger: next_step_unclear Recommend graceful failure.; situation=UNCERTAINTY; trigger=next_step_unclear |
| `retry` | none | - | - | - | 0 | False | - | situation=UNCERTAINTY; trigger=next_step_unclear |
| `backtrack` | none | - | - | - | 0 | False | - | situation=UNCERTAINTY; trigger=next_step_unclear |
| `consultation` | none | - | - | - | 1 | False | - | situation=UNCERTAINTY; trigger=next_step_unclear |
| `prediction_llm` | no_help | - | - | - | 24376 | False | INSUFFICIENT_CONTEXT | The advertised unlock operation requires a dyn:keyValue string, but the available RDF only identifies a fitting key resource at cells/8/4#key and provides no observed literal key value, so posting an invented value would be unsafe.; situation=UNCERTAINTY; trigger=next_step_unclear |

## Generated Artifacts

- `runs.csv`
- `agents.csv`
- `mase-events.csv`
- `mase-agent-moved.csv`
- `mase-transactions.csv`
- `cycle-durations.csv`
- `decisions.csv`
- `advisory-follow.csv`
- `contingency.csv`
- `opportunistic.csv`
- `actions.csv`
- `move-action-correlation.csv`
- `move-durations.csv`
- `java-library-evidence.csv`
- `move-duration-comparison.svg`
- `http-calls-by-move.svg`
- `cycle-duration-comparison.svg`
- `path-analysis-inputs/`
- `summary.json`
- `summary.md`

## Scope Notes

- This first report version intentionally reports only metrics with clear current sources.
- Java companion logs are reported as library evidence and are kept separate from React adapter selection metrics.
- BDI overrule and option-reordering metrics are not applicable to React advisory prompt injection.

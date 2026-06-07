# React Experiment Summary: react-ccrs-mazeV1-01-latest

Generated: 2026-06-07 19:45:00 +02:00

Run root: `S:\dev\ma\ccrs-react\experiments\runs\react-ccrs-mazeV1-01-latest`

Metric definitions: [METRICS.md](../../METRICS.md)

## Core Metrics

| Run | Agent | Graph | Mode | Reached exit | Total duration ms | Total moves | Avg agent cycle duration | Final cell |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `001-ccrs` | react_ccrs_mazeV1_01 | `graph_ccrs` | notebook | no | 2377574 | 120 | 3382.04 | `http://127.0.1.1:8080/cells/36/36` |

## Move Optimality

| Run | Agent | Optimal moves | Actual moves | Delta from optimal |
| --- | --- | --- | --- | --- |
| `001-ccrs` | react_ccrs_mazeV1_01 | 138 | 120 | - |

## Cycle Duration Summary

| Baseline avg ms | CCRS avg ms | CCRS opp 0 avg ms | CCRS opp 1 avg ms | CCRS opp 2 avg ms | CCRS opp 3 avg ms | CCRS opp 4 avg ms | CCRS cont invocation 1 avg ms | CCRS cont invocation 2 avg ms | CCRS cont invocation 3 avg ms | CCRS cont invocation 4 avg ms | CCRS cont invocation 5 avg ms | CCRS cont invocation 6 avg ms | CCRS cont invocation 7 avg ms | CCRS cont invocation 8 avg ms | CCRS cont invocation 9 avg ms | CCRS cont invocation 10 avg ms | CCRS cont invocation 11 avg ms | CCRS cont invocation 12 avg ms | CCRS cont invocation 13 avg ms | CCRS cont invocation 14 avg ms | CCRS cont invocation 15 avg ms | CCRS cont invocation 16 avg ms | CCRS cont invocation 17 avg ms | CCRS cont invocation 18 avg ms | CCRS cont invocation 19 avg ms | CCRS cont invocation 20 avg ms | CCRS cont invocation 21 avg ms | CCRS cont invocation 22 avg ms | CCRS cont invocation 23 avg ms | CCRS cont invocation 24 avg ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| - | 3382.04 | 3893.16 | 2340.69 | 2845.57 | 2908.69 | 2589.71 | 2614 | 3266 | 3345 | 4026 | 2273 | 2635 | 7242 | 4024 | 3289 | 3284 | 3798 | 3586 | 2268 | 3484 | 2357 | 2248 | 2885 | 2311 | 2145 | 3188 | 3889 | 3851 | 4155 | 3646 |

Opportunistic CCRS cycle averages exclude cycles where contingency CCRS was activated. Contingency columns are dynamically generated ordered invocation cycles, not counts per cycle.

## Advisory-Follow Evidence

| Run | Opp CCRS present | Selections | Selected rank 1 (highest) | Selected rank 2 | Selected rank 3 | Selected rank 4 | Selected none | Rank unavailable |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `001-ccrs` | 0 | 405 | - | - | - | - | - | - |
| `001-ccrs` | 1 | 64 | 45 | - | - | - | 19 | 0 |
| `001-ccrs` | 2 | 202 | 68 | 15 | - | - | 119 | 0 |
| `001-ccrs` | 3 | 26 | 16 | 2 | 1 | - | 7 | 0 |
| `001-ccrs` | 4 | 7 | 4 | 1 | 0 | 0 | 2 | 0 |

Ranks are inferred by joining each selection to `react.ccrs.opportunistic.detected` rows in the same run and cycle, ordered by descending utility. `Selected none` means the selected URI matched none of those ranked opportunistic targets.

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
- `java-library-evidence.csv`
- `path-analysis-inputs/`
- `summary.json`
- `summary.md`

## Scope Notes

- This first report version intentionally reports only metrics with clear current sources.
- Java companion logs are reported as library evidence and are kept separate from React adapter selection metrics.
- BDI overrule and option-reordering metrics are not applicable to React advisory prompt injection.

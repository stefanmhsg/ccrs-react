"""Black-box integration tests for the experiment report PowerShell scripts."""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "experiments" / "scripts"
POWERSHELL = (
    shutil.which("pwsh")
    or shutil.which("powershell.exe")
    or shutil.which("powershell")
)


def _read_json(path: Path) -> dict:
    with path.open(encoding="utf-8-sig") as stream:
        return json.load(stream)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


@unittest.skipUnless(POWERSHELL, "PowerShell is required for report script tests")
class ReportGenerationScriptsTest(unittest.TestCase):
    """Run the public script entry points against isolated fixture data."""

    def _run_script(
        self,
        script_name: str,
        *arguments: str,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        command = [
            str(POWERSHELL),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCRIPTS_DIR / script_name),
            *map(str, arguments),
        ]
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if check and result.returncode != 0:
            self.fail(
                f"{script_name} failed with exit code {result.returncode}\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )
        return result

    def test_prepare_current_run_refuses_to_clean_outside_runs_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            staging_dir = Path(temporary_dir) / "latest"
            staging_dir.mkdir()
            marker = staging_dir / "must-remain.txt"
            marker.write_text("preserve", encoding="utf-8")

            result = self._run_script(
                "prepare-current-run.ps1",
                "-StagingDir",
                str(staging_dir),
                check=False,
            )

            self.assertNotEqual(0, result.returncode)
            self.assertIn("outside experiments\\runs", result.stderr)
            self.assertEqual("preserve", marker.read_text(encoding="utf-8"))

    def test_import_manual_run_normalizes_exports_and_preserves_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            source_dir = root / "source"
            output_root = root / "runs"
            source_dir.mkdir()
            react_log = root / "fixture.log"
            java_log = root / "fixture.java.log"
            react_log.write_text("fixture react log\n", encoding="utf-8")
            java_log.write_text("fixture java log\n", encoding="utf-8")
            (source_dir / "notes.txt").write_text("fixture notes\n", encoding="utf-8")

            export_path = source_dir / "mase-viewer-export.json"
            export_path.write_text(
                json.dumps(
                    [
                        self._mase_event("AGENT_MOVED", "fixture-agent", "cells/0", 1),
                        self._mase_event("AGENT_MOVED", "fixture-agent", "cells/999", 2),
                    ]
                ),
                encoding="utf-8",
            )

            self._run_script(
                "import-manual-run.ps1",
                "-SourceDir",
                str(source_dir),
                "-OutputRoot",
                str(output_root),
                "-BatchId",
                "fixture-batch",
                "-RunId",
                "001-ccrs",
                "-AgentName",
                "fixture-agent",
                "-ReactLog",
                str(react_log),
                "-JavaLog",
                str(java_log),
                "-ScenarioId",
                "CcrsMazeV1",
                "-OptimalMoves",
                "2",
                "-ExitCell",
                "http://127.0.1.1:8080/cells/999",
                "-KeepSource",
            )

            run_dir = output_root / "fixture-batch" / "001-ccrs"
            run = _read_json(run_dir / "run.json")
            manifest = _read_json(output_root / "fixture-batch" / "manifest.json")
            normalized_events = (run_dir / "mase-events.jsonl").read_text(
                encoding="utf-8-sig"
            ).splitlines()

            self.assertEqual("fixture-agent", run["agentName"])
            self.assertEqual(2, run["maseCaptureEventCount"])
            self.assertEqual("completed", run["maseCaptureStatus"])
            self.assertEqual(["mase-viewer-export.json"], run["sourceExportFiles"])
            self.assertEqual(["notes.txt"], run["metadataFiles"])
            self.assertEqual(2, len(normalized_events))
            self.assertEqual(1, len(manifest["runs"]))
            self.assertTrue(export_path.exists())
            self.assertTrue((source_dir / "notes.txt").exists())
            self.assertTrue((run_dir / react_log.name).exists())
            self.assertTrue((run_dir / java_log.name).exists())

    def test_write_report_parses_fixture_batch_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            run_root = root / "fixture-mazev1"
            output_dir = root / "report"
            self._write_run(run_root, "001-baseline", "fixture-baseline", ccrs=False)
            self._write_run(run_root, "002-ccrs", "fixture-ccrs", ccrs=True)

            arguments = (
                "-BatchId",
                "fixture-mazev1",
                "-RunRoot",
                str(run_root),
                "-OutputDir",
                str(output_dir),
            )
            self._run_script("write-report.ps1", *arguments)
            first_summary = _read_json(output_dir / "summary.json")
            stale_path_input = output_dir / "path-analysis-inputs" / "stale.txt"
            stale_path_input.write_text("stale", encoding="utf-8")

            self._run_script("write-report.ps1", *arguments)
            summary = _read_json(output_dir / "summary.json")

            stable_fields = {
                key: summary[key]
                for key in (
                    "runCount",
                    "maseEventCount",
                    "decisionCount",
                    "contingencyRowCount",
                    "opportunisticRowCount",
                    "actionRowCount",
                    "moveActionCorrelationRowCount",
                    "moveDurationRowCount",
                    "zoneSummaryRowCount",
                    "javaEvidenceCount",
                )
            }
            self.assertEqual(
                stable_fields,
                {key: first_summary[key] for key in stable_fields},
            )
            self.assertEqual(2, summary["runCount"])
            self.assertEqual(6, summary["maseEventCount"])
            self.assertEqual(1, summary["decisionCount"])
            self.assertEqual(2, summary["contingencyRowCount"])
            self.assertEqual(1, summary["opportunisticRowCount"])
            self.assertEqual(4, summary["actionRowCount"])
            self.assertEqual(4, summary["moveActionCorrelationRowCount"])
            self.assertEqual(4, summary["moveDurationRowCount"])
            self.assertEqual(10, summary["zoneSummaryRowCount"])
            self.assertEqual(1, summary["javaEvidenceCount"])

            runs = {row["run_id"]: row for row in _read_csv(output_dir / "runs.csv")}
            decisions = _read_csv(output_dir / "decisions.csv")
            agents = _read_csv(output_dir / "agents.csv")
            self.assertEqual("selection_event", runs["002-ccrs"]["decision_metric_quality"])
            self.assertEqual("missing_selection_event", runs["001-baseline"]["decision_metric_quality"])
            self.assertEqual("True", decisions[0]["followed_top_opportunistic"])
            self.assertEqual({"2"}, {row["move_count"] for row in agents})
            self.assertFalse(stale_path_input.exists())

            path_inputs = list((output_dir / "path-analysis-inputs").glob("*.cells.txt"))
            self.assertEqual(2, len(path_inputs))
            for artifact in (
                "summary.md",
                "move-duration-comparison.svg",
                "http-calls-by-move.svg",
                "cycle-duration-comparison.svg",
            ):
                self.assertTrue((output_dir / artifact).is_file(), artifact)

            summary_markdown = (output_dir / "summary.md").read_text(
                encoding="utf-8-sig"
            )
            self.assertIn("fixture-mazev1", summary_markdown)
            self.assertIn("### Signifier Zone", summary_markdown)
            self.assertIn(
                "No `react.ccrs.opportunistic.selection` rows were found inside this zone window.",
                summary_markdown,
            )

    @staticmethod
    def _mase_event(
        event_type: str,
        agent: str,
        cell: str,
        sequence: int,
    ) -> dict:
        agent_uri = f"http://127.0.1.1:8080/agents/{agent}"
        cell_uri = f"http://127.0.1.1:8080/{cell}"
        timestamp = 9_000_000_000_000 + sequence * 1_000
        if event_type == "TRANSACTION":
            event = {
                "type": event_type,
                "agent": agent,
                "graph": cell_uri,
                "transactionId": sequence,
                "trigger": "POST",
                "status": "COMMITTED",
                "ruleCount": 1,
                "startedAt": timestamp - 10,
                "finishedAt": timestamp,
                "timestamp": timestamp,
            }
            return {
                "runId": "fixture-mase-run",
                "type": event_type,
                "timestamp": timestamp,
                "agent": agent,
                "graph": cell_uri,
                "transactionId": sequence,
                "event": event,
                "archiveId": sequence,
            }
        event = {
            "type": event_type,
            "agent": agent_uri,
            "cell": cell_uri,
            "timestamp": timestamp,
        }
        return {
            "runId": "fixture-mase-run",
            "type": event_type,
            "timestamp": timestamp,
            "agent": agent_uri,
            "cell": cell_uri,
            "transactionId": -1,
            "event": event,
            "archiveId": sequence,
        }

    def _write_run(
        self,
        run_root: Path,
        run_id: str,
        agent: str,
        *,
        ccrs: bool,
    ) -> None:
        run_dir = run_root / run_id
        run_dir.mkdir(parents=True)
        react_log_name = f"{agent}.log"
        java_log_name = f"{agent}.java.log" if ccrs else None
        run = {
            "batchId": "fixture-mazev1",
            "runId": run_id,
            "agentName": agent,
            "agentNames": [agent],
            "runMode": "ccrs" if ccrs else "baseline",
            "scenarioId": "CcrsMazeV1",
            "optimalMoves": 2,
            "exitCell": "http://127.0.1.1:8080/cells/999",
            "reactLogFile": react_log_name,
            "javaLogFile": java_log_name,
            "maseCaptureStatus": "completed",
            "maseCaptureEventCount": 4,
            "enableContingencyEscalationTool": ccrs,
        }
        (run_dir / "run.json").write_text(
            json.dumps(run, indent=2),
            encoding="utf-8",
        )

        log_lines = []
        if ccrs:
            log_lines.extend(
                [
                    "2026-01-01 12:00:00,000 [INFO] fixture: [REACT-CCRS-EVENT] event=react.ccrs.prompt_context.visible cycle=1 cycle_timestamp=2026-01-01T12:00:00+00:00 agent_name=fixture-ccrs opportunistic_count=1 contingency_guidance_count=0",
                    "2026-01-01 12:00:00,010 [INFO] fixture: [REACT-CCRS-EVENT] event=react.ccrs.opportunistic.detected cycle=1 cycle_timestamp=2026-01-01T12:00:00+00:00 agent_name=fixture-ccrs target=http://127.0.1.1:8080/cells/0 type=signifier utility=0.9",
                    "2026-01-01 12:00:00,020 [INFO] fixture: [REACT-CCRS-EVENT] event=react.ccrs.opportunistic.selection cycle=1 cycle_timestamp=2026-01-01T12:00:00+00:00 agent_name=fixture-ccrs tool_name=http_post tool_call_id=call-1 selected_uri=http://127.0.1.1:8080/cells/0 selection_mode=advisory_prompt opportunistic_count=1 contingency_guidance_count=0 followed_top_opportunistic=true followed_top_contingency_guidance=false followed_any_top_guidance=true top_opportunistic_target=http://127.0.1.1:8080/cells/0 top_contingency_guidance_target=null prompt_context_id=fixture-prompt",
                ]
            )
        log_lines.extend(
            [
                f"2026-01-01 12:00:00,100 [INFO] fixture: [REACT-CCRS-EVENT] event=react.loop.cycle cycle=1 cycle_timestamp=2026-01-01T12:00:00+00:00 agent_name={agent} tool_call_count=1",
                "2026-01-01 12:00:00,200 [INFO] fixture: [TOOL_NODE] Invoking tool: http_post with args: {'url': 'http://127.0.1.1:8080/cells/0'}",
                "2026-01-01 12:00:00,300 [INFO] fixture: [TOOL_NODE] Tool result: {\"content_type\": \"text/turtle\", \"http_ok\": true, \"http_status\": 200, \"method\": \"POST\", \"outcome\": \"success\", \"response_length\": 10, \"target\": \"http://127.0.1.1:8080/cells/0\", \"tool_call_id\": \"call-1\", \"tool_name\": \"http_post\"}",
            ]
        )
        if ccrs:
            log_lines.extend(
                [
                    "2026-01-01 12:00:01,000 [INFO] fixture: [REACT-CCRS-EVENT] event=react.ccrs.contingency.evaluate cycle=1 cycle_timestamp=2026-01-01T12:00:00+00:00 situation_type=FAILURE current_resource=http://127.0.1.1:8080/cells/0 evaluations=3",
                    "2026-01-01 12:00:01,100 [INFO] fixture: [REACT-CCRS-EVENT] event=react.ccrs.contingency.returned cycle=1 cycle_timestamp=2026-01-01T12:00:00+00:00 strategy_id=backtrack top_action=navigate target=http://127.0.1.1:8080/cells/999 suggestions=1 no_help=0",
                ]
            )
        log_lines.extend(
            [
                f"2026-01-01 12:00:02,100 [INFO] fixture: [REACT-CCRS-EVENT] event=react.loop.cycle cycle=2 cycle_timestamp=2026-01-01T12:00:02+00:00 agent_name={agent} tool_call_count=1",
                "2026-01-01 12:00:02,200 [INFO] fixture: [TOOL_NODE] Invoking tool: http_post with args: {'url': 'http://127.0.1.1:8080/cells/999'}",
                "2026-01-01 12:00:02,300 [INFO] fixture: [TOOL_NODE] Tool result: {\"content_type\": \"text/turtle\", \"http_ok\": true, \"http_status\": 200, \"method\": \"POST\", \"outcome\": \"success\", \"response_length\": 10, \"target\": \"http://127.0.1.1:8080/cells/999\", \"tool_call_id\": \"call-2\", \"tool_name\": \"http_post\"}",
            ]
        )
        (run_dir / react_log_name).write_text("\n".join(log_lines) + "\n", encoding="utf-8")

        if java_log_name:
            (run_dir / java_log_name).write_text(
                "2026-01-01 12:00:01,050 [JAVA-CCRS] fixture.BacktrackStrategy: evaluated fixture strategy\n",
                encoding="utf-8",
            )

        mase_events = [
            self._mase_event("AGENT_MOVED", agent, "cells/0", 1),
            self._mase_event("TRANSACTION", agent, "cells/0", 2),
            self._mase_event("AGENT_MOVED", agent, "cells/999", 3),
            self._mase_event("AGENT_MOVED", "unrelated-agent", "cells/7", 4),
        ]
        (run_dir / "mase-events.jsonl").write_text(
            "\n".join(json.dumps(event) for event in mase_events) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()

"""Trace identity logging without a graph, model or LangSmith network call."""
import asyncio
from contextlib import contextmanager
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

from langsmith.run_helpers import tracing_context
from react_agent import runner


class TraceIdentityTests(unittest.TestCase):
    @contextmanager
    def capture(self, current):
        with tracing_context(enabled=False), patch.object(runner, "get_current_run_tree", return_value=current), self.assertLogs("react_agent.runner", level="INFO") as logs:
            yield logs

    def record(self, logs):
        return json.loads(logs.output[0].split("[REACT-LANGSMITH] ", 1)[1])

    def test_sync_records_own_invocation_id_before_graph_failure(self):
        root, ancestor = uuid4(), uuid4()
        graph = SimpleNamespace(stream=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("synthetic graph failure")))
        with self.capture(SimpleNamespace(id=root, trace_id=ancestor)) as logs:
            with self.assertRaisesRegex(RuntimeError, "synthetic graph failure"):
                runner.run_query_sync(graph, "synthetic query", "agent_20260101_120000", {})
        record = self.record(logs)
        self.assertEqual(str(root), record["root_run_id"])
        self.assertEqual(str(ancestor), record["trace_id"])
        self.assertEqual("agent_20260101_120000", record["run_name"])
        terminal = logs.output[-1]
        self.assertIn('event=agent.run.finished',terminal)
        self.assertIn('timestamp_utc=',terminal)
        self.assertIn('reason=exception exception_type=RuntimeError',terminal)

    def test_async_records_id_without_network_or_agent_actions(self):
        root = uuid4()
        class Graph:
            async def astream(self, *args, **kwargs):
                yield {"messages": []}
        with self.capture(SimpleNamespace(id=root, trace_id=root)) as logs:
            asyncio.run(runner.run_query_async(Graph(), "query", "agent_run", {}))
        self.assertEqual(str(root), self.record(logs)["root_run_id"])
        self.assertIn('reason=graph_returned',logs.output[-1])

    def test_disabled_tracing_is_explicit_and_does_not_stop_execution(self):
        graph = SimpleNamespace(stream=lambda *args, **kwargs: iter([]))
        with self.capture(None) as logs:
            runner.run_query_sync(graph, "query", "agent_run", {})
        record = self.record(logs)
        self.assertEqual("unavailable", record["status"])
        self.assertIsNone(record["root_run_id"])

    def test_keyboard_interrupt_is_logged_and_propagated(self):
        graph = SimpleNamespace(stream=lambda *a, **kw: (_ for _ in ()).throw(KeyboardInterrupt()))
        with self.capture(None) as logs:
            with self.assertRaises(KeyboardInterrupt):
                runner.run_query_sync(graph,'query','fixture',{})
        self.assertIn('reason=interrupted exception_type=KeyboardInterrupt',logs.output[-1])


if __name__ == "__main__":
    unittest.main()

"""Export a LangSmith root run with its nested child runs as JSON."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from langsmith import Client


DEFAULT_OUTPUT_PATH = Path("langsmith_full_trace_tree.json")
UUID_PATTERN = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def extract_trace_id(value: str) -> str:
    """Return a trace UUID from either a raw UUID or a LangSmith run URL."""
    match = UUID_PATTERN.search(value)
    if match is None:
        raise ValueError(
            "Could not find a trace UUID. Pass the raw trace id or a LangSmith run URL."
        )
    return match.group(0)


def to_jsonable(obj: Any) -> Any:
    """Recursively convert LangSmith SDK objects into JSON-serializable data."""
    if obj is None:
        return None

    if isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, list):
        return [to_jsonable(item) for item in obj]

    if isinstance(obj, tuple):
        return [to_jsonable(item) for item in obj]

    if isinstance(obj, dict):
        return {str(key): to_jsonable(value) for key, value in obj.items()}

    if hasattr(obj, "model_dump"):
        return to_jsonable(obj.model_dump())

    if hasattr(obj, "dict"):
        return to_jsonable(obj.dict())

    return str(obj)


def export_trace(trace_id: str, output_path: Path) -> Path:
    """Download a root run and its hydrated child_runs tree, then save it."""
    client = Client()
    root_run = client.read_run(trace_id, load_child_runs=True)
    tree = to_jsonable(root_run)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(tree, indent=2, ensure_ascii=False),
        encoding="utf8",
    )
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export a LangSmith root trace with nested child_runs to JSON."
    )
    parser.add_argument(
        "trace",
        help="LangSmith trace UUID, or a run URL containing the UUID.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"JSON output path. Defaults to {DEFAULT_OUTPUT_PATH}.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    trace_id = extract_trace_id(args.trace)
    output_path = export_trace(trace_id, args.output)
    print(f"Saved full trace tree to {output_path.resolve()}")


if __name__ == "__main__":
    main()

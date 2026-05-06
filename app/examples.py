"""Helpers for saving repeatable demo artifacts."""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.schemas import WorkflowState


DEFAULT_EXAMPLES_DIR = Path("data/examples")


def example_slug(company_names: list[str]) -> str:
    joined = "_".join(company_names)
    slug = re.sub(r"[^a-z0-9]+", "_", joined.lower()).strip("_")
    return slug or "investment_research"


def save_example_artifacts(
    state: WorkflowState,
    examples_dir: Path = DEFAULT_EXAMPLES_DIR,
    name: str | None = None,
) -> Path:
    output_dir = examples_dir / (name or example_slug(state.raw_input))
    output_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "memo.md").write_text(state.memo, encoding="utf-8")
    (output_dir / "workflow_state.json").write_text(
        json.dumps(state.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    (output_dir / "run_log.json").write_text(
        json.dumps(state.run_log.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    return output_dir

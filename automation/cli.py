"""Command line interface for inspecting the automation pipeline."""

from __future__ import annotations

import argparse
import subprocess
from typing import Iterable, Sequence

from .pipeline import DEFAULT_FLAVORS, PipelinePlan, plan_for_flavors


def render_plan(plan: PipelinePlan) -> str:
    """Return a human-readable representation of a pipeline plan."""
    lines = [f"Flavor: {plan.flavor} (sha: {plan.sha})"]
    for stage in plan.stages:
        lines.append(f"  Stage: {stage.name}")
        for step in stage.steps:
            command_str = " ".join(step.command)
            lines.append(f"    - {step.label}: {command_str}")
    return "\n".join(lines)


def _execute_plan(plan: PipelinePlan) -> None:
    """Run each command in the given pipeline plan sequentially."""
    for stage in plan.stages:
        for step in stage.steps:
            subprocess.run(step.command, check=True)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="automation-cli", description="Automation pipeline planning utility."
    )
    parser.add_argument(
        "--flavors",
        nargs="+",
        help="Override flavors to plan (default: dev stg prod).",
    )
    parser.add_argument(
        "--sha",
        help="Use a specific git SHA. Defaults to current HEAD.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute the commands sequentially instead of printing the plan.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Entrypoint for the CLI."""
    args = _parse_args(argv)
    flavors: Iterable[str] = args.flavors if args.flavors else DEFAULT_FLAVORS
    plans = plan_for_flavors(tuple(flavors), sha=args.sha)
    if args.execute:
        for plan in plans:
            _execute_plan(plan)
        return 0
    for plan in plans:
        print(render_plan(plan))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

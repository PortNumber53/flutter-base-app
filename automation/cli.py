"""Command line interface for inspecting the automation pipeline."""

from __future__ import annotations

import argparse
import subprocess
from typing import Iterable, Sequence

from .pipeline import DEFAULT_FLAVORS, PipelinePlan, build_pipeline_plan, plan_for_flavors
from .config_fetcher import main as config_fetcher_main


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
        "--admin-api-url",
        help="Admin Dashboard API URL for fetching feature config.",
    )
    parser.add_argument(
        "--admin-api-key",
        help="API key for Admin Dashboard authentication.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute the commands sequentially instead of printing the plan.",
    )
    
    # Add subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Pipeline subcommand (default behavior)
    pipeline_parser = subparsers.add_parser("pipeline", help="Show pipeline plan")
    pipeline_parser.add_argument(
        "--flavors",
        nargs="+",
        help="Override flavors to plan (default: dev stg prod).",
    )
    pipeline_parser.add_argument(
        "--sha",
        help="Use a specific git SHA. Defaults to current HEAD.",
    )
    pipeline_parser.add_argument(
        "--admin-api-url",
        help="Admin Dashboard API URL.",
    )
    pipeline_parser.add_argument(
        "--admin-api-key",
        help="API key for Admin Dashboard.",
    )
    pipeline_parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute the pipeline commands.",
    )
    
    # Config subcommand
    config_parser = subparsers.add_parser("config", help="Fetch configuration")
    config_parser.add_argument(
        "--env",
        required=True,
        choices=["dev", "stg", "prod"],
        help="Target environment",
    )
    config_parser.add_argument(
        "--api",
        help="Admin Dashboard API URL",
    )
    config_parser.add_argument(
        "--api-key",
        help="API key for authentication",
    )
    config_parser.add_argument(
        "--output",
        help="Output directory for config files",
    )
    config_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be written without writing",
    )
    
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Entrypoint for the CLI."""
    args = _parse_args(argv)
    
    # Handle subcommands
    if args.command == "config":
        return config_fetcher_main([
            "--env", args.env,
            *("--api", args.api) if args.api else [],
            *("--api-key", args.api_key) if args.api_key else [],
            *("--output", args.output) if args.output else [],
            *("--dry-run",) if args.dry_run else [],
        ])
    
    # Default: pipeline command
    flavors: Iterable[str] = args.flavors if args.flavors else DEFAULT_FLAVORS
    
    # Build plans with optional config fetch
    plans = [
        build_pipeline_plan(
            flavor,
            sha=args.sha,
            admin_api_url=args.admin_api_url,
            admin_api_key=args.admin_api_key,
        )
        for flavor in flavors
    ]
    
    if args.execute:
        for plan in plans:
            _execute_plan(plan)
        return 0
    
    for plan in plans:
        print(render_plan(plan))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

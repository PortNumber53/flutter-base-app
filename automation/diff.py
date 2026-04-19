"""Feature flag diff tool for comparing configurations between environments.

Compares feature flag configurations between environments to catch drift
and ensure consistency before promotion.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from .config_fetcher import ConfigExport, FeatureFlag


@dataclass
class FeatureDiff:
    """Difference for a single feature flag."""

    key: str
    env1_value: bool | None = None
    env2_value: bool | None = None
    env1_rules: list[dict[str, Any]] = field(default_factory=list)
    env2_rules: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class DiffReport:
    """Complete diff report between two environments."""

    compared_at: str
    environment_1: str
    environment_2: str
    summary: dict[str, list[str]] = field(default_factory=dict)
    details: list[FeatureDiff] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "compared_at": self.compared_at,
            "environment_1": self.environment_1,
            "environment_2": self.environment_2,
            "summary": self.summary,
            "details": [
                {
                    "key": d.key,
                    "env1_value": d.env1_value,
                    "env2_value": d.env2_value,
                    "env1_rules": d.env1_rules,
                    "env2_rules": d.env2_rules,
                }
                for d in self.details
            ],
        }


def load_config(config_path: Path | None, env: str) -> ConfigExport | None:
    """Load configuration from file or mock data.

    Args:
        config_path: Path to config file, or None to use mock
        env: Environment name

    Returns:
        ConfigExport or None if file not found
    """
    if config_path is None:
        # Use mock data from mock_admin_server
        from .mock_admin_server import MOCK_FEATURES

        features = [
            FeatureFlag.from_dict(f) for f in MOCK_FEATURES.get(env, [])
        ]
        return ConfigExport(
            environment=env,
            exported_at=datetime.now(timezone.utc).isoformat(),
            features=tuple(features),
        )

    if not config_path.exists():
        return None

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return ConfigExport(
            environment=data.get("environment", env),
            exported_at=data.get("exportedAt", ""),
            features=tuple(
                FeatureFlag.from_dict(f) for f in data.get("features", [])
            ),
            signature=data.get("signature"),
        )
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Error loading {config_path}: {e}", file=sys.stderr)
        return None


def compare_configs(
    env1: str, env2: str, config1: ConfigExport, config2: ConfigExport
) -> DiffReport:
    """Compare two configurations and generate a diff report.

    Args:
        env1: First environment name
        env2: Second environment name
        config1: First configuration
        config2: Second configuration

    Returns:
        DiffReport with comparison results
    """
    report = DiffReport(
        compared_at=datetime.now(timezone.utc).isoformat(),
        environment_1=env1,
        environment_2=env2,
        summary={
            "added_in_env2": [],
            "removed_in_env2": [],
            "modified": [],
            "same": [],
        },
    )

    # Build feature maps
    features1 = {f.key: f for f in config1.features}
    features2 = {f.key: f for f in config2.features}

    # Find added/removed
    keys1 = set(features1.keys())
    keys2 = set(features2.keys())

    report.summary["added_in_env2"] = sorted(keys2 - keys1)
    report.summary["removed_in_env2"] = sorted(keys1 - keys2)

    # Compare common features
    for key in sorted(keys1 & keys2):
        f1 = features1[key]
        f2 = features2[key]

        # Check if modified
        if f1.value != f2.value or f1.rules != f2.rules:
            report.summary["modified"].append(key)
            report.details.append(
                FeatureDiff(
                    key=key,
                    env1_value=f1.value,
                    env2_value=f2.value,
                    env1_rules=list(f1.rules),
                    env2_rules=list(f2.rules),
                )
            )
        else:
            report.summary["same"].append(key)

    return report


def is_allowed_drift(key: str, patterns: list[str]) -> bool:
    """Check if a key matches any of the allowed drift patterns.

    Args:
        key: Feature key to check
        patterns: List of glob patterns (e.g., "debug.*", "beta.*")

    Returns:
        True if key matches any pattern
    """
    for pattern in patterns:
        if fnmatch.fnmatch(key, pattern):
            return True
    return False


def print_diff(report: DiffReport, verbose: bool = False) -> None:
    """Print a human-readable diff report.

    Args:
        report: DiffReport to print
        verbose: Whether to print detailed diff for each feature
    """
    print(f"\nDiff: {report.environment_1} → {report.environment_2}")
    print(f"Compared at: {report.compared_at}\n")

    # Summary
    added = report.summary.get("added_in_env2", [])
    removed = report.summary.get("removed_in_env2", [])
    modified = report.summary.get("modified", [])
    same = report.summary.get("same", [])

    if added:
        print(f"Added in {report.environment_2} ({len(added)}):")
        for key in added:
            print(f"  + {key}")
        print()

    if removed:
        print(f"Removed in {report.environment_2} ({len(removed)}):")
        for key in removed:
            print(f"  - {key}")
        print()

    if modified:
        print(f"Modified ({len(modified)}):")
        for key in modified:
            print(f"  ~ {key}")
        print()

    if same:
        print(f"Same ({len(same)}): {', '.join(same[:5])}", end="")
        if len(same) > 5:
            print(f" and {len(same) - 5} more")
        else:
            print()
        print()

    # Detailed differences
    if verbose and report.details:
        print("Detailed Changes:")
        print("-" * 50)
        for diff in report.details:
            print(f"\n{diff.key}:")
            print(f"  {report.environment_1}: {diff.env1_value}")
            print(f"  {report.environment_2}: {diff.env2_value}")
            if diff.env1_rules != diff.env2_rules:
                print(f"  Rules changed:")
                print(f"    Before: {diff.env1_rules}")
                print(f"    After:  {diff.env2_rules}")


def main(argv: Sequence[str] | None = None) -> int:
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        prog="diff",
        description="Compare feature flag configurations between environments",
    )
    parser.add_argument(
        "--env1",
        required=True,
        choices=["dev", "stg", "prod"],
        help="First environment to compare",
    )
    parser.add_argument(
        "--env2",
        required=True,
        choices=["dev", "stg", "prod"],
        help="Second environment to compare",
    )
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=Path("./config"),
        help="Directory containing feature_flags_*.json files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Export diff report to JSON file",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed differences",
    )
    parser.add_argument(
        "--fail-on-drift",
        action="store_true",
        help="Exit with error code if configurations differ",
    )
    parser.add_argument(
        "--allowed-drift-keys",
        help="Comma-separated glob patterns for allowed drift (e.g., 'debug.*,beta.*')",
    )

    args = parser.parse_args(argv)

    # Load configs
    config1_path = args.config_dir / f"feature_flags_{args.env1}.json"
    config2_path = args.config_dir / f"feature_flags_{args.env2}.json"

    config1 = load_config(config1_path if config1_path.exists() else None, args.env1)
    config2 = load_config(config2_path if config2_path.exists() else None, args.env2)

    if config1 is None:
        print(f"Error: Could not load config for {args.env1}", file=sys.stderr)
        return 1
    if config2 is None:
        print(f"Error: Could not load config for {args.env2}", file=sys.stderr)
        return 1

    # Compare
    report = compare_configs(args.env1, args.env2, config1, config2)

    # Print report
    print_diff(report, verbose=args.verbose)

    # Export if requested
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)
        print(f"\nReport exported to: {args.output}")

    # Determine exit code
    if args.fail_on_drift:
        allowed_patterns = []
        if args.allowed_drift_keys:
            allowed_patterns = [p.strip() for p in args.allowed_drift_keys.split(",")]

        # Check for non-allowed drift
        drift_found = False
        for key in report.summary.get("added_in_env2", []):
            if not is_allowed_drift(key, allowed_patterns):
                drift_found = True
                break
        for key in report.summary.get("removed_in_env2", []):
            if not is_allowed_drift(key, allowed_patterns):
                drift_found = True
                break
        for key in report.summary.get("modified", []):
            if not is_allowed_drift(key, allowed_patterns):
                drift_found = True
                break

        if drift_found:
            print("\nError: Configuration drift detected!")
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

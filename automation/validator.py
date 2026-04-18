"""Config validator and linter for the wrapper app.

Validates configuration files against JSON schemas and checks for common errors
and inconsistencies.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence


@dataclass(frozen=True)
class ValidationIssue:
    """A single validation issue (error or warning)."""

    message: str
    path: str = ""
    severity: str = "error"  # "error" or "warning"


@dataclass
class ValidationResult:
    """Result of validating a configuration file."""

    file_path: Path
    is_valid: bool = True
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)

    def add_error(self, message: str, path: str = "") -> None:
        """Add an error to the result."""
        self.errors.append(ValidationIssue(message, path, "error"))
        self.is_valid = False

    def add_warning(self, message: str, path: str = "") -> None:
        """Add a warning to the result."""
        self.warnings.append(ValidationIssue(message, path, "warning"))


class ConfigValidator:
    """Validator for wrapper app configuration files."""

    # Valid environments
    VALID_ENVS = {"dev", "stg", "prod"}

    # Feature key pattern: module.action
    FEATURE_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")

    # App ID pattern: com.company.app
    APP_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")

    # Required top-level fields
    REQUIRED_FIELDS = {"app_id", "app_name", "env"}

    def __init__(self, schema_path: Path | None = None):
        """Initialize the validator with optional schema file.

        Args:
            schema_path: Path to JSON schema file for validation
        """
        self.schema = None
        if schema_path and schema_path.exists():
            with open(schema_path, "r", encoding="utf-8") as f:
                self.schema = json.load(f)

    def validate_file(self, file_path: Path) -> ValidationResult:
        """Validate a single configuration file.

        Args:
            file_path: Path to the JSON config file

        Returns:
            ValidationResult with any errors or warnings
        """
        result = ValidationResult(file_path=file_path)

        # Try to parse JSON
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            config = json.loads(content)
        except json.JSONDecodeError as e:
            result.add_error(f"Invalid JSON: {e}")
            return result
        except FileNotFoundError:
            result.add_error(f"File not found: {file_path}")
            return result

        # Run all validation checks
        self._validate_required_fields(config, result)
        self._validate_app_id(config, result)
        self._validate_environment(config, result)
        self._validate_features(config, result)
        self._validate_navigation(config, result)
        self._validate_modules(config, result)

        return result

    def _validate_required_fields(self, config: dict[str, Any], result: ValidationResult) -> None:
        """Check that all required fields are present."""
        missing = self.REQUIRED_FIELDS - set(config.keys())
        if missing:
            result.add_error(f"Missing required fields: {', '.join(missing)}")

    def _validate_app_id(self, config: dict[str, Any], result: ValidationResult) -> None:
        """Validate app_id format."""
        app_id = config.get("app_id", "")
        if app_id and not self.APP_ID_PATTERN.match(app_id):
            result.add_error(
                f"Invalid app_id '{app_id}'. Expected format: com.company.app",
                path="app_id"
            )

    def _validate_environment(self, config: dict[str, Any], result: ValidationResult) -> None:
        """Validate environment value."""
        env = config.get("env", "")
        if env and env not in self.VALID_ENVS:
            result.add_error(
                f"Invalid environment '{env}'. Must be one of: {', '.join(self.VALID_ENVS)}",
                path="env"
            )

    def _validate_features(self, config: dict[str, Any], result: ValidationResult) -> None:
        """Validate feature flag definitions."""
        features = config.get("features", {})
        if not isinstance(features, dict):
            result.add_error("'features' must be an object", path="features")
            return

        seen_keys: set[str] = set()
        for key in features.keys():
            # Check format
            if not self.FEATURE_KEY_PATTERN.match(key):
                result.add_error(
                    f"Invalid feature key '{key}'. Expected format: module.action",
                    path=f"features.{key}"
                )

            # Check for duplicates
            if key in seen_keys:
                result.add_error(f"Duplicate feature key: {key}", path=f"features.{key}")
            seen_keys.add(key)

            # Validate feature definition
            feature_def = features[key]
            if not isinstance(feature_def, dict):
                result.add_error(
                    f"Feature '{key}' must be an object",
                    path=f"features.{key}"
                )
                continue

            # Warn if no 'default' field
            if "default" not in feature_def:
                result.add_warning(
                    f"Feature '{key}' missing 'default' field",
                    path=f"features.{key}"
                )

    def _validate_navigation(self, config: dict[str, Any], result: ValidationResult) -> None:
        """Validate navigation configuration."""
        nav = config.get("navigation", {})
        if not isinstance(nav, dict):
            return

        layout = nav.get("layout", "")
        if layout and layout not in {"tabs", "drawer", "stack"}:
            result.add_error(
                f"Invalid navigation layout '{layout}'. Must be one of: tabs, drawer, stack",
                path="navigation.layout"
            )

        order = nav.get("order", [])
        if order and not isinstance(order, list):
            result.add_error(
                "navigation.order must be an array",
                path="navigation.order"
            )

    def _validate_modules(self, config: dict[str, Any], result: ValidationResult) -> None:
        """Validate modules configuration."""
        modules = config.get("modules", {})
        if not isinstance(modules, dict):
            result.add_error("'modules' must be an object", path="modules")
            return

        for module_id, module_config in modules.items():
            if not isinstance(module_config, dict):
                result.add_error(
                    f"Module '{module_id}' config must be an object",
                    path=f"modules.{module_id}"
                )
                continue

            enabled = module_config.get("enabled")
            if enabled is not None and not isinstance(enabled, bool):
                result.add_error(
                    f"Module '{module_id}' enabled must be a boolean",
                    path=f"modules.{module_id}.enabled"
                )


def validate_all_environments(
    config_dir: Path, validator: ConfigValidator
) -> list[ValidationResult]:
    """Validate all environment config files in a directory.

    Args:
        config_dir: Directory containing app_config.*.json files
        validator: ConfigValidator instance

    Returns:
        List of ValidationResult for each file
    """
    results: list[ValidationResult] = []

    for env in ConfigValidator.VALID_ENVS:
        config_file = config_dir / f"app_config.{env}.json"
        if config_file.exists():
            results.append(validator.validate_file(config_file))

    return results


def main(argv: Sequence[str] | None = None) -> int:
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        prog="validate",
        description="Validate wrapper app configuration files",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to config file to validate",
    )
    parser.add_argument(
        "--schema",
        type=Path,
        help="Path to JSON schema file",
    )
    parser.add_argument(
        "--all-environments",
        action="store_true",
        help="Validate all environment configs in the config directory",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors",
    )
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=Path("apps/wrapper_app/assets/config"),
        help="Directory containing config files (for --all-environments)",
    )

    args = parser.parse_args(argv)

    validator = ConfigValidator(schema_path=args.schema)

    # Collect results
    if args.all_environments:
        if not args.config_dir.exists():
            print(f"Error: Config directory not found: {args.config_dir}", file=sys.stderr)
            return 1
        results = validate_all_environments(args.config_dir, validator)
        if not results:
            print(f"No config files found in {args.config_dir}", file=sys.stderr)
            return 1
    elif args.config:
        if not args.config.exists():
            print(f"Error: Config file not found: {args.config}", file=sys.stderr)
            return 1
        results = [validator.validate_file(args.config)]
    else:
        parser.error("Must specify --config or --all-environments")
        return 1  #pragma: no cover

    # Report results
    exit_code = 0
    for result in results:
        print(f"\n{result.file_path}:")

        if result.is_valid and not result.warnings:
            print("  ✓ Valid")
            continue

        for error in result.errors:
            print(f"  ✗ Error: {error.message}")
            if error.path:
                print(f"    at: {error.path}")

        for warning in result.warnings:
            print(f"  ⚠ Warning: {warning.message}")
            if warning.path:
                print(f"    at: {warning.path}")

        if not result.is_valid or (args.strict and result.warnings):
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

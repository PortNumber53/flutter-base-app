"""Config fetcher for fetching feature flags from Admin Dashboard API.

This module handles fetching feature flag configuration from the Admin Dashboard
during the CI/CD build process. The configuration is embedded into the app binary
and serves as the default/fallback configuration at runtime.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


DEFAULT_ADMIN_API_URL = "https://admin-api.example.com"


@dataclass(frozen=True)
class ConfigFetchError(Exception):
    """Error occurred while fetching configuration."""

    message: str


@dataclass(frozen=True)
class FeatureFlag:
    """Represents a feature flag with rules."""

    key: str
    value: bool
    rules: tuple[dict[str, Any], ...]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FeatureFlag:
        """Create FeatureFlag from dictionary."""
        return cls(
            key=data["key"],
            value=data.get("value", False),
            rules=tuple(data.get("rules", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "key": self.key,
            "value": self.value,
            "rules": list(self.rules),
        }


@dataclass(frozen=True)
class ConfigExport:
    """Complete configuration export from Admin Dashboard."""

    environment: str
    exported_at: str
    features: tuple[FeatureFlag, ...]
    signature: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "environment": self.environment,
            "exportedAt": self.exported_at,
            "features": [f.to_dict() for f in self.features],
            "signature": self.signature,
        }

    def compute_signature(self) -> str:
        """Compute SHA256 signature of the config content (excluding existing signature)."""
        content = json.dumps(
            {
                "environment": self.environment,
                "exportedAt": self.exported_at,
                "features": [f.to_dict() for f in self.features],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return f"sha256:{hashlib.sha256(content.encode()).hexdigest()}"


def fetch_config_from_api(
    api_url: str, api_key: str, environment: str
) -> ConfigExport:
    """Fetch configuration from Admin Dashboard API.
    
    Args:
        api_url: Base URL of the Admin Dashboard API
        api_key: API key for authentication
        environment: Target environment (dev, stg, prod)
    
    Returns:
        ConfigExport with feature flags for the environment
    
    Raises:
        ConfigFetchError: If the API request fails
    """
    url = f"{api_url.rstrip('/')}/v1/config/{environment}"
    
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "flutter-base-app-automation/1.0",
        },
    )
    
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status != 200:
                raise ConfigFetchError(
                    f"API returned status {response.status}"
                )
            
            data = json.loads(response.read().decode("utf-8"))
            
            features = tuple(
                FeatureFlag.from_dict(f) for f in data.get("features", [])
            )
            
            return ConfigExport(
                environment=environment,
                exported_at=data.get("exportedAt", ""),
                features=features,
                signature=data.get("signature"),
            )
    except urllib.error.HTTPError as e:
        raise ConfigFetchError(
            f"HTTP error {e.code}: {e.reason}"
        ) from e
    except urllib.error.URLError as e:
        raise ConfigFetchError(
            f"Failed to connect to API: {e.reason}"
        ) from e
    except json.JSONDecodeError as e:
        raise ConfigFetchError(
            f"Invalid JSON response: {e}"
        ) from e


def validate_config(config: ConfigExport) -> list[str]:
    """Validate configuration and return list of warnings/errors.
    
    Args:
        config: The configuration to validate
    
    Returns:
        List of validation issues (empty if valid)
    """
    issues: list[str] = []
    
    # Validate signature if present
    if config.signature:
        expected = config.compute_signature()
        if config.signature != expected:
            issues.append(
                f"Signature mismatch: expected {expected}, got {config.signature}"
            )
    
    # Check for duplicate feature keys
    keys = [f.key for f in config.features]
    duplicates = {k for k in keys if keys.count(k) > 1}
    if duplicates:
        issues.append(f"Duplicate feature keys: {', '.join(duplicates)}")
    
    # Validate environment
    valid_envs = {"dev", "stg", "prod"}
    if config.environment not in valid_envs:
        issues.append(
            f"Invalid environment '{config.environment}', expected one of {valid_envs}"
        )
    
    return issues


def write_config_files(
    config: ConfigExport, output_dir: Path
) -> tuple[Path, Path]:
    """Write configuration files to output directory.
    
    Args:
        config: Configuration to write
        output_dir: Directory to write files to
    
    Returns:
        Tuple of (config_path, features_path)
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Write full config export
    config_path = output_dir / f"feature_flags_{config.environment}.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config.to_dict(), f, indent=2)
    
    # Write simplified features map for app consumption
    features_path = output_dir / "exported_features.json"
    features_map = {f.key: f.value for f in config.features}
    with open(features_path, "w", encoding="utf-8") as f:
        json.dump(features_map, f, indent=2)
    
    # Also write environment-specific app_config
    app_config = {
        "app_id": "com.company.wrapper",
        "app_name": "Wrapper App",
        "env": config.environment,
        "features": {
            f.key: {"default": f.value} for f in config.features
        },
        "exported_at": config.exported_at,
    }
    app_config_path = output_dir / f"app_config.{config.environment}.json"
    with open(app_config_path, "w", encoding="utf-8") as f:
        json.dump(app_config, f, indent=2)
    
    return config_path, features_path


def main(argv: Sequence[str] | None = None) -> int:
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        prog="config-fetcher",
        description="Fetch feature flags from Admin Dashboard API",
    )
    parser.add_argument(
        "--env",
        required=True,
        choices=["dev", "stg", "prod"],
        help="Target environment to fetch config for",
    )
    parser.add_argument(
        "--api",
        default=DEFAULT_ADMIN_API_URL,
        help=f"Admin Dashboard API base URL (default: {DEFAULT_ADMIN_API_URL})",
    )
    parser.add_argument(
        "--api-key",
        required=True,
        help="API key for Admin Dashboard authentication",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("./config"),
        help="Output directory for config files (default: ./config)",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate existing config without fetching",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be written without writing files",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    
    args = parser.parse_args(argv)
    
    try:
        if args.validate_only:
            # Validate existing config
            config_path = args.output / f"feature_flags_{args.env}.json"
            if not config_path.exists():
                print(f"Error: Config file not found: {config_path}", file=sys.stderr)
                return 1
            
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            config = ConfigExport(
                environment=data["environment"],
                exported_at=data["exportedAt"],
                features=tuple(FeatureFlag.from_dict(f) for f in data["features"]),
                signature=data.get("signature"),
            )
            
            issues = validate_config(config)
            if issues:
                print(f"Validation failed for {args.env}:")
                for issue in issues:
                    print(f"  - {issue}")
                return 1
            
            print(f"✓ Config for {args.env} is valid")
            print(f"  Features: {len(config.features)}")
            print(f"  Exported: {config.exported_at}")
            return 0
        
        # Fetch config from API
        if args.verbose:
            print(f"Fetching config for environment: {args.env}")
            print(f"API URL: {args.api}")
        
        config = fetch_config_from_api(args.api, args.api_key, args.env)
        
        if args.verbose:
            print(f"Fetched {len(config.features)} feature flags")
            print(f"Exported at: {config.exported_at}")
        
        # Validate
        issues = validate_config(config)
        if issues:
            print(f"Validation failed:", file=sys.stderr)
            for issue in issues:
                print(f"  - {issue}", file=sys.stderr)
            return 1
        
        if args.dry_run:
            print(f"Would write config to: {args.output}")
            print(f"Features: {len(config.features)}")
            for feature in config.features:
                print(f"  - {feature.key}: {feature.value}")
            return 0
        
        # Write files
        config_path, features_path = write_config_files(config, args.output)
        
        print(f"✓ Config written for {args.env}")
        print(f"  Full export: {config_path}")
        print(f"  Features map: {features_path}")
        print(f"  Features: {len(config.features)}")
        
        return 0
        
    except ConfigFetchError as e:
        print(f"Error: {e.message}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

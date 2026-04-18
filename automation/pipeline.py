"""Automation pipeline planning utilities for the Flutter wrapper app."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence, Tuple


@dataclass(frozen=True)
class PipelineStep:
    """Atomic command to run inside the pipeline."""

    label: str
    command: Tuple[str, ...]
    description: str


@dataclass(frozen=True)
class PipelineStage:
    """Collection of ordered steps grouped by concern."""

    name: str
    steps: Tuple[PipelineStep, ...]


@dataclass(frozen=True)
class PipelinePlan:
    """Full pipeline definition for a flavor."""

    flavor: str
    sha: str
    stages: Tuple[PipelineStage, ...]


DEFAULT_FLAVORS: Tuple[str, ...] = ("dev", "stg", "prod")
_ARTIFACT_EXTENSIONS = {"android": "aab", "ios": "ipa"}


def artifact_name(platform: str, flavor: str, sha: str) -> str:
    """Compute the artifact name using flavor and git SHA metadata."""
    ext = _ARTIFACT_EXTENSIONS.get(platform)
    if ext is None:
        raise ValueError(f"Unsupported platform '{platform}'")
    sanitized_sha = sha or "unknown"
    return f"wrapper-{flavor}-{sanitized_sha}.{ext}"


def build_pipeline_plan(
    flavor: str,
    sha: str | None = None,
    admin_api_url: str | None = None,
    admin_api_key: str | None = None,
) -> PipelinePlan:
    """Create the ordered pipeline plan for a single flavor.
    
    Args:
        flavor: Build flavor (dev, stg, prod)
        sha: Git SHA for artifact naming (auto-detected if None)
        admin_api_url: Admin Dashboard API URL for fetching config
        admin_api_key: API key for Admin Dashboard authentication
    """
    resolved_sha = sha or _current_git_sha()

    # Config fetch requires API credentials
    config_fetch_set = admin_api_url is not None and admin_api_key is not None

    verification_steps: Tuple[PipelineStep, ...] = (
        PipelineStep(
            label="format",
            command=("dart", "format", "--output=none", "--set-exit-if-changed", "."),
            description="Fail if code is not dart-formatted.",
        ),
        PipelineStep(
            label="analyze",
            command=("flutter", "analyze"),
            description="Static analysis for the Flutter app.",
        ),
        PipelineStep(
            label="test",
            command=("flutter", "test", "--coverage"),
            description="Run unit/widget tests with coverage.",
        ),
    )

    # Config fetch step - fetches feature flags from Admin Dashboard
    if config_fetch_set:
        config_steps: Tuple[PipelineStep, ...] = (
            PipelineStep(
                label="fetch-config",
                command=(
                    "python",
                    "-m",
                    "automation.config_fetcher",
                    "--env",
                    flavor,
                    "--api",
                    admin_api_url,
                    "--api-key",
                    admin_api_key,
                    "--output",
                    "apps/wrapper_app/assets/config/",
                ),
                description="Fetch feature flags from Admin Dashboard API.",
            ),
        )
    else:
        config_steps = (
            PipelineStep(
                label="fetch-config-skipped",
                command=("echo", "Skipping config fetch (no API credentials)"),
                description="Config fetch skipped. Using local fallback config.",
            ),
        )

    android_steps: Tuple[PipelineStep, ...] = (
        PipelineStep(
            label="android-build",
            command=(
                "bundle",
                "exec",
                "fastlane",
                "android",
                "build",
                f"flavor:{flavor}",
                f"output:{artifact_name('android', flavor, resolved_sha)}",
            ),
            description="Build Android AAB via Fastlane with flavor metadata.",
        ),
    )
    ios_steps: Tuple[PipelineStep, ...] = (
        PipelineStep(
            label="ios-build",
            command=(
                "bundle",
                "exec",
                "fastlane",
                "ios",
                "build",
                f"flavor:{flavor}",
                f"output:{artifact_name('ios', flavor, resolved_sha)}",
            ),
            description="Build iOS IPA via Fastlane with flavor metadata.",
        ),
    )
    stages: Tuple[PipelineStage, ...] = (
        PipelineStage(name="verification", steps=verification_steps),
        PipelineStage(name="config-fetch", steps=config_steps),
        PipelineStage(name="android", steps=android_steps),
        PipelineStage(name="ios", steps=ios_steps),
    )
    return PipelinePlan(flavor=flavor, sha=resolved_sha, stages=stages)


def plan_for_flavors(
    flavors: Sequence[str], sha: str | None = None
) -> Tuple[PipelinePlan, ...]:
    """Return pipeline plans for multiple flavors."""
    return tuple(build_pipeline_plan(flavor, sha) for flavor in flavors)


def _current_git_sha() -> str:
    """Return short git SHA, falling back to 'unknown' on error."""
    try:
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.check_output(
            ("git", "rev-parse", "--short", "HEAD"),
            cwd=str(repo_root),
            stderr=subprocess.DEVNULL,
        )
        return result.decode("utf-8").strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"

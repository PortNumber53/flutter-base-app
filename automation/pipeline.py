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


def build_pipeline_plan(flavor: str, sha: str | None = None) -> PipelinePlan:
    """Create the ordered pipeline plan for a single flavor."""
    resolved_sha = sha or _current_git_sha()
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

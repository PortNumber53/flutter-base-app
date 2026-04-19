"""Automation package for the Flutter wrapper app.

Provides tooling for:
- CI/CD pipeline planning and execution
- Feature flag configuration management
- Config validation and linting
- Environment diff checks
- User entitlement simulation
- Module scaffolding
"""

__version__ = "1.0.0"

from .cli import main
from .config_fetcher import ConfigFetchError, ConfigExport, FeatureFlag
from .create_module import create_module_structure, ModuleConfig
from .diff import DiffReport, compare_configs
from .pipeline import PipelinePlan, PipelineStage, PipelineStep, build_pipeline_plan
from .simulate import SimulationContext, PERSONAS
from .validator import ConfigValidator, ValidationResult

__all__ = [
    "main",
    "ConfigFetchError",
    "ConfigExport",
    "FeatureFlag",
    "create_module_structure",
    "ModuleConfig",
    "DiffReport",
    "compare_configs",
    "PipelinePlan",
    "PipelineStage",
    "PipelineStep",
    "build_pipeline_plan",
    "SimulationContext",
    "PERSONAS",
    "ConfigValidator",
    "ValidationResult",
]

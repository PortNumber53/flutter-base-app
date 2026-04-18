"""Tests for the config validator."""

import json
import tempfile
from pathlib import Path

import pytest

from automation.validator import (
    ConfigValidator,
    ValidationIssue,
    ValidationResult,
)


class TestValidationIssue:
    def test_validation_issue_creation(self):
        issue = ValidationIssue("Test message", "path.to.field", "error")
        assert issue.message == "Test message"
        assert issue.path == "path.to.field"
        assert issue.severity == "error"

    def test_validation_issue_defaults(self):
        issue = ValidationIssue("Test message")
        assert issue.message == "Test message"
        assert issue.path == ""
        assert issue.severity == "error"


class TestValidationResult:
    def test_initial_state_is_valid(self):
        result = ValidationResult(file_path=Path("test.json"))
        assert result.is_valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0

    def test_add_error_makes_invalid(self):
        result = ValidationResult(file_path=Path("test.json"))
        result.add_error("Error message")

        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0].message == "Error message"

    def test_add_warning_keeps_valid(self):
        result = ValidationResult(file_path=Path("test.json"))
        result.add_warning("Warning message")

        assert result.is_valid is True
        assert len(result.warnings) == 1
        assert result.warnings[0].message == "Warning message"


class TestConfigValidator:
    @pytest.fixture
    def validator(self):
        return ConfigValidator()

    def create_temp_config(self, content: dict) -> Path:
        """Create a temporary config file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(content, f)
            return Path(f.name)

    def test_valid_config(self, validator):
        config = {
            "app_id": "com.company.test",
            "app_name": "Test App",
            "env": "dev",
            "features": {
                "test.feature": {"default": True}
            }
        }
        config_path = self.create_temp_config(config)

        result = validator.validate_file(config_path)

        assert result.is_valid is True
        assert len(result.errors) == 0

        # Cleanup
        config_path.unlink()

    def test_missing_required_fields(self, validator):
        config = {
            "app_name": "Test App",
            # Missing app_id and env
        }
        config_path = self.create_temp_config(config)

        result = validator.validate_file(config_path)

        assert result.is_valid is False
        assert any("app_id" in e.message for e in result.errors)
        assert any("env" in e.message for e in result.errors)

        config_path.unlink()

    def test_invalid_app_id(self, validator):
        config = {
            "app_id": "invalid-id",
            "app_name": "Test",
            "env": "dev",
        }
        config_path = self.create_temp_config(config)

        result = validator.validate_file(config_path)

        assert result.is_valid is False
        assert any("app_id" in e.message for e in result.errors)

        config_path.unlink()

    def test_invalid_environment(self, validator):
        config = {
            "app_id": "com.company.test",
            "app_name": "Test",
            "env": "invalid_env",
        }
        config_path = self.create_temp_config(config)

        result = validator.validate_file(config_path)

        assert result.is_valid is False
        assert any("environment" in e.message for e in result.errors)

        config_path.unlink()

    def test_invalid_feature_key_format(self, validator):
        config = {
            "app_id": "com.company.test",
            "app_name": "Test",
            "env": "dev",
            "features": {
                "invalid_feature_key": {"default": True}
            }
        }
        config_path = self.create_temp_config(config)

        result = validator.validate_file(config_path)

        assert result.is_valid is False
        assert any("feature key" in e.message for e in result.errors)

        config_path.unlink()

    def test_valid_feature_key_format(self, validator):
        config = {
            "app_id": "com.company.test",
            "app_name": "Test",
            "env": "dev",
            "features": {
                "module.action": {"default": True},
                "auth.login": {"default": True},
            }
        }
        config_path = self.create_temp_config(config)

        result = validator.validate_file(config_path)

        assert result.is_valid is True

        config_path.unlink()

    def test_missing_default_field_warning(self, validator):
        config = {
            "app_id": "com.company.test",
            "app_name": "Test",
            "env": "dev",
            "features": {
                "module.action": {}  # Missing default
            }
        }
        config_path = self.create_temp_config(config)

        result = validator.validate_file(config_path)

        assert result.is_valid is True  # Still valid
        assert len(result.warnings) > 0
        assert any("default" in w.message for w in result.warnings)

        config_path.unlink()

    def test_invalid_navigation_layout(self, validator):
        config = {
            "app_id": "com.company.test",
            "app_name": "Test",
            "env": "dev",
            "navigation": {
                "layout": "invalid_layout"
            }
        }
        config_path = self.create_temp_config(config)

        result = validator.validate_file(config_path)

        assert result.is_valid is False
        assert any("layout" in e.message for e in result.errors)

        config_path.unlink()

    def test_file_not_found(self, validator):
        result = validator.validate_file(Path("/nonexistent/file.json"))

        assert result.is_valid is False
        assert any("not found" in e.message for e in result.errors)

    def test_invalid_json(self, validator):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write("{invalid json")
            config_path = Path(f.name)

        result = validator.validate_file(config_path)

        assert result.is_valid is False
        assert any("Invalid JSON" in e.message for e in result.errors)

        config_path.unlink()

"""Tests for the config validator."""

import json
import tempfile
from pathlib import Path
import unittest

from automation.validator import (
    ConfigValidator,
    ValidationIssue,
    ValidationResult,
)


class TestValidationIssue(unittest.TestCase):
    def test_validation_issue_creation(self):
        issue = ValidationIssue("Test message", "path.to.field", "error")
        self.assertEqual(issue.message, "Test message")
        self.assertEqual(issue.path, "path.to.field")
        self.assertEqual(issue.severity, "error")

    def test_validation_issue_defaults(self):
        issue = ValidationIssue("Test message")
        self.assertEqual(issue.message, "Test message")
        self.assertEqual(issue.path, "")
        self.assertEqual(issue.severity, "error")


class TestValidationResult(unittest.TestCase):
    def test_initial_state_is_valid(self):
        result = ValidationResult(file_path=Path("test.json"))
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.warnings), 0)

    def test_add_error_makes_invalid(self):
        result = ValidationResult(file_path=Path("test.json"))
        result.add_error("Error message")

        self.assertFalse(result.is_valid)
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(result.errors[0].message, "Error message")

    def test_add_warning_keeps_valid(self):
        result = ValidationResult(file_path=Path("test.json"))
        result.add_warning("Warning message")

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(result.warnings[0].message, "Warning message")


class TestConfigValidator(unittest.TestCase):
    def setUp(self):
        self.validator = ConfigValidator()

    def create_temp_config(self, content: dict) -> Path:
        """Create a temporary config file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(content, f)
        return Path(f.name)

    def test_valid_config(self):
        config = {
            "app_id": "com.company.test",
            "app_name": "Test App",
            "env": "dev",
            "features": {
                "test.feature": {"default": True}
            }
        }
        config_path = self.create_temp_config(config)

        result = self.validator.validate_file(config_path)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

        # Cleanup
        config_path.unlink()

    def test_missing_required_fields(self):
        config = {
            "app_name": "Test App",
            # Missing app_id and env
        }
        config_path = self.create_temp_config(config)

        result = self.validator.validate_file(config_path)

        self.assertFalse(result.is_valid)
        self.assertTrue(any("app_id" in e.message for e in result.errors))
        self.assertTrue(any("env" in e.message for e in result.errors))

        config_path.unlink()

    def test_invalid_app_id(self):
        config = {
            "app_id": "invalid-id",
            "app_name": "Test",
            "env": "dev",
        }
        config_path = self.create_temp_config(config)

        result = self.validator.validate_file(config_path)

        self.assertFalse(result.is_valid)
        self.assertTrue(any("app_id" in e.message for e in result.errors))

        config_path.unlink()

    def test_invalid_environment(self):
        config = {
            "app_id": "com.company.test",
            "app_name": "Test",
            "env": "invalid_env",
        }
        config_path = self.create_temp_config(config)

        result = self.validator.validate_file(config_path)

        self.assertFalse(result.is_valid)
        self.assertTrue(any("environment" in e.message for e in result.errors))

        config_path.unlink()

    def test_invalid_feature_key_format(self):
        config = {
            "app_id": "com.company.test",
            "app_name": "Test",
            "env": "dev",
            "features": {
                "invalid_feature_key": {"default": True}
            }
        }
        config_path = self.create_temp_config(config)

        result = self.validator.validate_file(config_path)

        self.assertFalse(result.is_valid)
        self.assertTrue(any("feature key" in e.message for e in result.errors))

        config_path.unlink()

    def test_valid_feature_key_format(self):
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

        result = self.validator.validate_file(config_path)

        self.assertTrue(result.is_valid)

        config_path.unlink()

    def test_missing_default_field_warning(self):
        config = {
            "app_id": "com.company.test",
            "app_name": "Test",
            "env": "dev",
            "features": {
                "module.action": {}  # Missing default
            }
        }
        config_path = self.create_temp_config(config)

        result = self.validator.validate_file(config_path)

        self.assertTrue(result.is_valid)  # Still valid
        self.assertTrue(len(result.warnings) > 0)
        self.assertTrue(any("default" in w.message for w in result.warnings))

        config_path.unlink()

    def test_invalid_navigation_layout(self):
        config = {
            "app_id": "com.company.test",
            "app_name": "Test",
            "env": "dev",
            "navigation": {
                "layout": "invalid_layout"
            }
        }
        config_path = self.create_temp_config(config)

        result = self.validator.validate_file(config_path)

        self.assertFalse(result.is_valid)
        self.assertTrue(any("layout" in e.message for e in result.errors))

        config_path.unlink()

    def test_file_not_found(self):
        result = self.validator.validate_file(Path("/nonexistent/file.json"))

        self.assertFalse(result.is_valid)
        self.assertTrue(any("not found" in e.message for e in result.errors))

    def test_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{invalid json")
        config_path = Path(f.name)

        result = self.validator.validate_file(config_path)

        self.assertFalse(result.is_valid)
        self.assertTrue(any("Invalid JSON" in e.message for e in result.errors))

        config_path.unlink()


if __name__ == "__main__":
    unittest.main()

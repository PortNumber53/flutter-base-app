"""Tests for the config_fetcher module."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from automation.config_fetcher import (
    ConfigExport,
    ConfigFetchError,
    FeatureFlag,
    fetch_config_from_api,
    validate_config,
    write_config_files,
)


class TestFeatureFlag(unittest.TestCase):
    """Test FeatureFlag dataclass."""

    def test_from_dict_basic(self) -> None:
        """Test creating FeatureFlag from dict."""
        data = {"key": "chat.view", "value": True, "rules": []}
        flag = FeatureFlag.from_dict(data)

        self.assertEqual(flag.key, "chat.view")
        self.assertEqual(flag.value, True)
        self.assertEqual(flag.rules, ())

    def test_from_dict_with_rules(self) -> None:
        """Test creating FeatureFlag with rules."""
        data = {
            "key": "forms.advanced",
            "value": False,
            "rules": [{"if": {"plan": "pro"}, "value": True}],
        }
        flag = FeatureFlag.from_dict(data)

        self.assertEqual(flag.key, "forms.advanced")
        self.assertEqual(flag.value, False)
        self.assertEqual(len(flag.rules), 1)
        self.assertEqual(flag.rules[0]["if"]["plan"], "pro")

    def test_to_dict(self) -> None:
        """Test converting FeatureFlag to dict."""
        flag = FeatureFlag(key="test.feature", value=True, rules=())
        result = flag.to_dict()

        self.assertEqual(result["key"], "test.feature")
        self.assertEqual(result["value"], True)
        self.assertEqual(result["rules"], [])


class TestConfigExport(unittest.TestCase):
    """Test ConfigExport dataclass."""

    def test_to_dict(self) -> None:
        """Test converting ConfigExport to dict."""
        config = ConfigExport(
            environment="dev",
            exported_at="2025-01-15T10:00:00Z",
            features=(
                FeatureFlag(key="chat.view", value=True, rules=()),
            ),
        )
        result = config.to_dict()

        self.assertEqual(result["environment"], "dev")
        self.assertEqual(result["exportedAt"], "2025-01-15T10:00:00Z")
        self.assertEqual(len(result["features"]), 1)
        self.assertIsNone(result["signature"])

    def test_compute_signature(self) -> None:
        """Test computing SHA256 signature."""
        config = ConfigExport(
            environment="prod",
            exported_at="2025-01-15T10:00:00Z",
            features=(
                FeatureFlag(key="chat.view", value=True, rules=()),
            ),
        )
        signature = config.compute_signature()

        self.assertTrue(signature.startswith("sha256:"))
        self.assertEqual(len(signature), 7 + 64)  # "sha256:" + 64 hex chars


class TestValidateConfig(unittest.TestCase):
    """Test config validation."""

    def test_valid_config(self) -> None:
        """Test valid config has no issues."""
        config = ConfigExport(
            environment="dev",
            exported_at="2025-01-15T10:00:00Z",
            features=(
                FeatureFlag(key="chat.view", value=True, rules=()),
            ),
        )
        issues = validate_config(config)

        self.assertEqual(issues, [])

    def test_duplicate_keys(self) -> None:
        """Test detection of duplicate feature keys."""
        config = ConfigExport(
            environment="dev",
            exported_at="2025-01-15T10:00:00Z",
            features=(
                FeatureFlag(key="chat.view", value=True, rules=()),
                FeatureFlag(key="chat.view", value=False, rules=()),
            ),
        )
        issues = validate_config(config)

        self.assertEqual(len(issues), 1)
        self.assertIn("Duplicate feature keys: chat.view", issues)

    def test_invalid_environment(self) -> None:
        """Test validation of environment name."""
        config = ConfigExport(
            environment="invalid",
            exported_at="2025-01-15T10:00:00Z",
            features=(),
        )
        issues = validate_config(config)

        self.assertEqual(len(issues), 1)
        self.assertIn("Invalid environment 'invalid'", issues[0])

    def test_signature_mismatch(self) -> None:
        """Test detection of signature mismatch."""
        config = ConfigExport(
            environment="dev",
            exported_at="2025-01-15T10:00:00Z",
            features=(),
            signature="sha256:invalid123",
        )
        issues = validate_config(config)

        self.assertEqual(len(issues), 1)
        self.assertIn("Signature mismatch", issues[0])


class TestWriteConfigFiles(unittest.TestCase):
    """Test writing config files."""

    def setUp(self) -> None:
        """Create temporary directory for test files."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_write_files(self) -> None:
        """Test writing config files."""
        config = ConfigExport(
            environment="dev",
            exported_at="2025-01-15T10:00:00Z",
            features=(
                FeatureFlag(key="chat.view", value=True, rules=()),
                FeatureFlag(key="forms.submit", value=False, rules=()),
            ),
        )

        config_path, features_path = write_config_files(config, self.temp_dir)

        # Check files exist
        self.assertTrue(config_path.exists())
        self.assertTrue(features_path.exists())

        # Check exported_features.json content
        with open(features_path) as f:
            features_map = json.load(f)
        self.assertEqual(features_map["chat.view"], True)
        self.assertEqual(features_map["forms.submit"], False)


class TestFetchConfigFromApi(unittest.TestCase):
    """Test fetching config from API."""

    @patch("automation.config_fetcher.urllib.request.urlopen")
    def test_successful_fetch(self, mock_urlopen: MagicMock) -> None:
        """Test successful API fetch."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({
            "environment": "dev",
            "exportedAt": "2025-01-15T10:00:00Z",
            "features": [
                {"key": "chat.view", "value": True, "rules": []},
            ],
        }).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_response

        config = fetch_config_from_api(
            "https://api.example.com",
            "test-api-key",
            "dev",
        )

        self.assertEqual(config.environment, "dev")
        self.assertEqual(len(config.features), 1)
        self.assertEqual(config.features[0].key, "chat.view")

    @patch("automation.config_fetcher.urllib.request.urlopen")
    def test_http_error(self, mock_urlopen: MagicMock) -> None:
        """Test handling of HTTP error."""
        from urllib.error import HTTPError
        mock_urlopen.side_effect = HTTPError(
            "https://api.example.com/v1/config/dev",
            401,
            "Unauthorized",
            {},
            None,
        )

        with self.assertRaises(ConfigFetchError) as ctx:
            fetch_config_from_api(
                "https://api.example.com",
                "bad-api-key",
                "dev",
            )
        self.assertIn("401", str(ctx.exception))

    @patch("automation.config_fetcher.urllib.request.urlopen")
    def test_invalid_json(self, mock_urlopen: MagicMock) -> None:
        """Test handling of invalid JSON response."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b"not valid json"
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with self.assertRaises(ConfigFetchError) as ctx:
            fetch_config_from_api(
                "https://api.example.com",
                "test-api-key",
                "dev",
            )
        self.assertIn("Invalid JSON", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

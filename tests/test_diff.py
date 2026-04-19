"""Tests for the config diff tool."""

import json
import tempfile
from pathlib import Path
import unittest

from automation.diff import (
    DiffReport,
    FeatureDiff,
    compare_configs,
    is_allowed_drift,
    load_config,
)
from automation.simulate import parse_entitlements
from automation.config_fetcher import ConfigExport, FeatureFlag


class TestFeatureDiff(unittest.TestCase):
    def test_feature_diff_creation(self):
        diff = FeatureDiff(
            key="test.feature",
            env1_value=True,
            env2_value=False,
            env1_rules=[],
            env2_rules=[{"if": {"plan": "pro"}, "value": True}],
        )
        self.assertEqual(diff.key, "test.feature")
        self.assertTrue(diff.env1_value)
        self.assertFalse(diff.env2_value)


class TestDiffReport(unittest.TestCase):
    def test_diff_report_to_dict(self):
        report = DiffReport(
            compared_at="2025-01-01T00:00:00Z",
            environment_1="dev",
            environment_2="prod",
            summary={
                "added_in_env2": ["feature.new"],
                "removed_in_env2": ["feature.old"],
                "modified": ["feature.changed"],
                "same": ["feature.same"],
            },
            details=[
                FeatureDiff(
                    key="feature.changed",
                    env1_value=True,
                    env2_value=False,
                    env1_rules=[],
                    env2_rules=[],
                )
            ],
        )

        data = report.to_dict()

        self.assertEqual(data["compared_at"], "2025-01-01T00:00:00Z")
        self.assertEqual(data["environment_1"], "dev")
        self.assertEqual(data["environment_2"], "prod")
        self.assertEqual(len(data["details"]), 1)


class TestLoadConfig(unittest.TestCase):
    def test_load_from_file(self):
        config_data = {
            "environment": "dev",
            "exportedAt": "2025-01-01T00:00:00Z",
            "features": [
                {"key": "test.feature", "value": True, "rules": []}
            ],
            "signature": "sha256:abc123",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
        config_path = Path(f.name)

        config = load_config(config_path, "dev")

        self.assertIsNotNone(config)
        self.assertEqual(config.environment, "dev")
        self.assertEqual(len(config.features), 1)
        self.assertEqual(config.features[0].key, "test.feature")

        config_path.unlink()

    def test_load_from_mock(self):
        config = load_config(None, "dev")

        self.assertIsNotNone(config)
        self.assertEqual(config.environment, "dev")
        self.assertTrue(len(config.features) > 0)

    def test_load_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{invalid")
        config_path = Path(f.name)

        config = load_config(config_path, "dev")

        self.assertIsNone(config)

        config_path.unlink()


class TestCompareConfigs(unittest.TestCase):
    def test_no_difference(self):
        features = [FeatureFlag("test.feature", True, ())]
        config1 = ConfigExport("dev", "2025-01-01T00:00:00Z", tuple(features))
        config2 = ConfigExport("prod", "2025-01-01T00:00:00Z", tuple(features))

        report = compare_configs("dev", "prod", config1, config2)

        self.assertEqual(len(report.summary["same"]), 1)
        self.assertEqual(len(report.summary["added_in_env2"]), 0)
        self.assertEqual(len(report.summary["removed_in_env2"]), 0)
        self.assertEqual(len(report.summary["modified"]), 0)
        self.assertEqual(len(report.details), 0)

    def test_feature_added(self):
        config1 = ConfigExport("dev", "2025-01-01T00:00:00Z",
            tuple([FeatureFlag("old.feature", True, ())]))
        config2 = ConfigExport("prod", "2025-01-01T00:00:00Z",
            tuple([
                FeatureFlag("old.feature", True, ()),
                FeatureFlag("new.feature", True, ()),
            ]))

        report = compare_configs("dev", "prod", config1, config2)

        self.assertIn("new.feature", report.summary["added_in_env2"])
        self.assertIn("old.feature", report.summary["same"])

    def test_feature_removed(self):
        config1 = ConfigExport("dev", "2025-01-01T00:00:00Z",
            tuple([
                FeatureFlag("old.feature", True, ()),
                FeatureFlag("removed.feature", True, ()),
            ]))
        config2 = ConfigExport("prod", "2025-01-01T00:00:00Z",
            tuple([FeatureFlag("old.feature", True, ())]))

        report = compare_configs("dev", "prod", config1, config2)

        self.assertIn("removed.feature", report.summary["removed_in_env2"])
        self.assertIn("old.feature", report.summary["same"])

    def test_feature_modified(self):
        config1 = ConfigExport("dev", "2025-01-01T00:00:00Z",
            tuple([FeatureFlag("test.feature", True, ())]))
        config2 = ConfigExport("prod", "2025-01-01T00:00:00Z",
            tuple([FeatureFlag("test.feature", False, ())]))

        report = compare_configs("dev", "prod", config1, config2)

        self.assertIn("test.feature", report.summary["modified"])
        self.assertEqual(len(report.details), 1)
        self.assertTrue(report.details[0].env1_value)
        self.assertFalse(report.details[0].env2_value)

    def test_rules_changed(self):
        config1 = ConfigExport("dev", "2025-01-01T00:00:00Z",
            tuple([FeatureFlag("test.feature", True, ())]))
        config2 = ConfigExport("prod", "2025-01-01T00:00:00Z",
            tuple([FeatureFlag("test.feature", True,
                ({"if": {"plan": "pro"}, "value": True},))]))

        report = compare_configs("dev", "prod", config1, config2)

        self.assertIn("test.feature", report.summary["modified"])


class TestIsAllowedDrift(unittest.TestCase):
    def test_exact_match(self):
        self.assertTrue(is_allowed_drift("debug.feature", ["debug.*"]))
        self.assertTrue(is_allowed_drift("beta.test", ["beta.*"]))

    def test_no_match(self):
        self.assertFalse(is_allowed_drift("production.feature", ["debug.*"]))
        self.assertFalse(is_allowed_drift("chat.view", ["debug.*"]))

    def test_multiple_patterns(self):
        self.assertTrue(is_allowed_drift("debug.feature", ["debug.*", "beta.*"]))
        self.assertTrue(is_allowed_drift("beta.feature", ["debug.*", "beta.*"]))
        self.assertFalse(is_allowed_drift("other.feature", ["debug.*", "beta.*"]))

    def test_empty_patterns(self):
        self.assertFalse(is_allowed_drift("any.feature", []))


class TestParseEntitlements(unittest.TestCase):
    def test_single_entitlement(self):
        result = parse_entitlements("chat.view:true")
        self.assertEqual(result, {"chat.view": True})

    def test_multiple_entitlements(self):
        result = parse_entitlements("chat.view:true,forms.advanced:false")
        self.assertEqual(result, {"chat.view": True, "forms.advanced": False})

    def test_without_value(self):
        result = parse_entitlements("feature.flag")
        self.assertEqual(result, {"feature.flag": True})

    def test_numeric_true(self):
        result = parse_entitlements("flag:1")
        self.assertEqual(result, {"flag": True})

    def test_empty_string(self):
        result = parse_entitlements("")
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()

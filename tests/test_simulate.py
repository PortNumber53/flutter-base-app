"""Tests for the entitlements simulator."""

import json
import tempfile
from pathlib import Path
import unittest

from automation.simulate import (
    SimulationContext,
    merge_with_persona,
    export_simulation,
    load_simulation,
    parse_entitlements,
    print_simulation,
    main,
    PERSONAS,
)


class TestParseEntitlements(unittest.TestCase):
    def test_simple_entitlement(self):
        result = parse_entitlements("chat.view:true")
        self.assertEqual(result, {"chat.view": True})

    def test_entitlement_no_value(self):
        result = parse_entitlements("chat.view")
        self.assertEqual(result, {"chat.view": True})

    def test_multiple_entitlements(self):
        result = parse_entitlements(
            "chat.view:true,forms.advanced:false,auth.mfa"
        )
        self.assertEqual(result, {
            "chat.view": True,
            "forms.advanced": False,
            "auth.mfa": True,
        })

    def test_numeric_true(self):
        result = parse_entitlements("flag:1")
        self.assertEqual(result, {"flag": True})

    def test_numeric_false(self):
        result = parse_entitlements("flag:0")
        self.assertEqual(result, {"flag": False})

    def test_boolean_yes(self):
        result = parse_entitlements("flag:yes")
        self.assertEqual(result, {"flag": True})

    def test_boolean_on(self):
        result = parse_entitlements("flag:on")
        self.assertEqual(result, {"flag": True})

    def test_empty_string(self):
        result = parse_entitlements("")
        self.assertEqual(result, {})


class TestSimulationContext(unittest.TestCase):
    def test_from_dict(self):
        data = {
            "plan": "pro",
            "roles": ["admin", "member"],
            "org_id": "org_123",
            "user_id": "user_456",
            "entitlements": {"chat.view": True}
        }
        ctx = SimulationContext.from_dict(data)
        self.assertEqual(ctx.plan, "pro")
        self.assertEqual(ctx.roles, ["admin", "member"])
        self.assertEqual(ctx.org_id, "org_123")
        self.assertEqual(ctx.user_id, "user_456")
        self.assertEqual(ctx.entitlements, {"chat.view": True})

    def test_from_dict_defaults(self):
        data = {}
        ctx = SimulationContext.from_dict(data)
        self.assertEqual(ctx.plan, "free")
        self.assertEqual(ctx.roles, ["member"])
        self.assertEqual(ctx.org_id, "org_simulated")
        self.assertEqual(ctx.user_id, "user_simulated")
        self.assertEqual(ctx.entitlements, {})

    def test_to_dict(self):
        ctx = SimulationContext(
            plan="enterprise",
            roles=["admin"],
            org_id="org_789",
            user_id="user_999",
            entitlements={"forms.advanced": True}
        )
        data = ctx.to_dict()
        self.assertEqual(data["plan"], "enterprise")
        self.assertEqual(data["roles"], ["admin"])
        self.assertEqual(data["org_id"], "org_789")
        self.assertEqual(data["user_id"], "user_999")
        self.assertEqual(data["entitlements"], {"forms.advanced": True})


class TestMergeWithPersona(unittest.TestCase):
    def test_merge_nothing(self):
        base = PERSONAS["free_user"]
        result = merge_with_persona(base)
        self.assertEqual(result.plan, "free")
        self.assertEqual(result.roles, ["member"])

    def test_merge_plan(self):
        base = PERSONAS["free_user"]
        result = merge_with_persona(base, plan="pro")
        self.assertEqual(result.plan, "pro")
        self.assertEqual(result.roles, ["member"])

    def test_merge_roles(self):
        base = PERSONAS["free_user"]
        result = merge_with_persona(base, roles=["admin", "beta"])
        self.assertEqual(result.roles, ["admin", "beta"])

    def test_merge_entitlements(self):
        base = PERSONAS["free_user"]
        result = merge_with_persona(base, entitlements={"new.feature": True})
        self.assertTrue(result.entitlements["new.feature"])
        # Original entitlements preserved
        self.assertTrue(result.entitlements["home.view"])


class TestPersonas(unittest.TestCase):
    def test_free_user_exists(self):
        self.assertIn("free_user", PERSONAS)
        ctx = PERSONAS["free_user"]
        self.assertEqual(ctx.plan, "free")
        self.assertFalse(ctx.entitlements["chat.view"])

    def test_pro_admin_exists(self):
        self.assertIn("pro_admin", PERSONAS)
        ctx = PERSONAS["pro_admin"]
        self.assertEqual(ctx.plan, "pro")
        self.assertIn("admin", ctx.roles)
        self.assertTrue(ctx.entitlements["chat.view"])

    def test_pro_member_exists(self):
        self.assertIn("pro_member", PERSONAS)
        ctx = PERSONAS["pro_member"]
        self.assertEqual(ctx.plan, "pro")
        self.assertTrue(ctx.entitlements["chat.view"])
        self.assertFalse(ctx.entitlements["chat.reply"])

    def test_enterprise_member_exists(self):
        self.assertIn("enterprise_member", PERSONAS)
        ctx = PERSONAS["enterprise_member"]
        self.assertEqual(ctx.plan, "enterprise")
        self.assertTrue(ctx.entitlements["analytics.view"])

    def test_guest_exists(self):
        self.assertIn("guest", PERSONAS)
        ctx = PERSONAS["guest"]
        self.assertEqual(ctx.roles, [])
        self.assertEqual(ctx.org_id, "")
        self.assertFalse(ctx.entitlements["home.view"])

    def test_beta_user_exists(self):
        self.assertIn("beta_user", PERSONAS)
        ctx = PERSONAS["beta_user"]
        self.assertIn("beta_tester", ctx.roles)
        self.assertTrue(ctx.entitlements["beta.feature"])


class TestExportAndLoad(unittest.TestCase):
    def test_export_and_load_roundtrip(self):
        original = SimulationContext(
            plan="pro",
            roles=["admin"],
            org_id="org_test",
            user_id="user_test",
            entitlements={"feature.a": True, "feature.b": False}
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "simulation.json"
            export_simulation(original, path)

            # Verify file exists
            self.assertTrue(path.exists())

            # Load and compare
            loaded = load_simulation(path)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.plan, original.plan)
            self.assertEqual(loaded.roles, original.roles)
            self.assertEqual(loaded.org_id, original.org_id)
            self.assertEqual(loaded.user_id, original.user_id)
            self.assertEqual(loaded.entitlements, original.entitlements)

    def test_load_nonexistent_file(self):
        result = load_simulation(Path("/nonexistent/file.json"))
        self.assertIsNone(result)

    def test_load_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{invalid json")
        path = Path(f.name)

        result = load_simulation(path)
        self.assertIsNone(result)

        path.unlink()


class TestMain(unittest.TestCase):
    def test_list_personas(self):
        result = main(["--list-personas"])
        self.assertEqual(result, 0)

    def test_print_free_user_persona(self):
        result = main(["--persona", "free_user"])
        self.assertEqual(result, 0)

    def test_custom_persona(self):
        result = main([
            "--plan", "pro",
            "--roles", "admin,member",
            "--entitlements", "custom.feature:true"
        ])
        self.assertEqual(result, 0)

    def test_export_and_load_persona(self):
        with tempfile.TemporaryDirectory() as tmp:
            export_path = Path(tmp) / "test.json"

            # Export
            result = main([
                "--persona", "pro_admin",
                "--export", str(export_path)
            ])
            self.assertEqual(result, 0)
            self.assertTrue(export_path.exists())

            # Load and print
            result = main(["--load", str(export_path)])
            self.assertEqual(result, 0)

    def test_export_json_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            export_path = Path(tmp) / "test.json"

            result = main([
                "--persona", "free_user",
                "--export", str(export_path),
                "--format", "json"
            ])
            self.assertEqual(result, 0)

    def test_load_invalid_file(self):
        result = main(["--load", "/nonexistent/file.json"])
        self.assertEqual(result, 1)


if __name__ == "__main__":
    unittest.main()

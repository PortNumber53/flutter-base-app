"""Tests for the entitlement simulator."""

import json
import tempfile
from pathlib import Path

import pytest

from automation.simulate import (
    PERSONAS,
    SimulationContext,
    export_simulation,
    load_simulation,
    merge_with_persona,
    parse_entitlements,
)


class TestSimulationContext:
    def test_context_creation(self):
        context = SimulationContext(
            plan="pro",
            roles=["admin", "member"],
            org_id="org_test",
            user_id="user_001",
            entitlements={"test.feature": True},
        )

        assert context.plan == "pro"
        assert context.roles == ["admin", "member"]
        assert context.org_id == "org_test"
        assert context.user_id == "user_001"
        assert context.entitlements == {"test.feature": True}

    def test_to_dict(self):
        context = SimulationContext(
            plan="pro",
            roles=["admin"],
            org_id="org_test",
            user_id="user_001",
            entitlements={"feature": True},
        )

        data = context.to_dict()

        assert data["plan"] == "pro"
        assert data["roles"] == ["admin"]
        assert data["org_id"] == "org_test"
        assert data["user_id"] == "user_001"
        assert data["entitlements"] == {"feature": True}

    def test_from_dict(self):
        data = {
            "plan": "enterprise",
            "roles": ["member", "admin"],
            "org_id": "org_abc",
            "user_id": "user_xyz",
            "entitlements": {"chat.view": True},
        }

        context = SimulationContext.from_dict(data)

        assert context.plan == "enterprise"
        assert context.roles == ["member", "admin"]
        assert context.org_id == "org_abc"
        assert context.user_id == "user_xyz"
        assert context.entitlements == {"chat.view": True}


class TestPersonas:
    def test_free_user_persona(self):
        persona = PERSONAS["free_user"]
        assert persona.plan == "free"
        assert "member" in persona.roles
        assert persona.entitlements["chat.view"] is False
        assert persona.entitlements["forms.submit"] is True

    def test_pro_admin_persona(self):
        persona = PERSONAS["pro_admin"]
        assert persona.plan == "pro"
        assert "admin" in persona.roles
        assert persona.entitlements["chat.reply"] is True

    def test_pro_member_persona(self):
        persona = PERSONAS["pro_member"]
        assert persona.plan == "pro"
        assert "member" in persona.roles
        assert persona.entitlements["chat.reply"] is False

    def test_guest_persona(self):
        persona = PERSONAS["guest"]
        assert persona.plan == "free"
        assert len(persona.roles) == 0
        assert persona.entitlements["home.view"] is False


class TestParseEntitlements:
    def test_single_with_value(self):
        result = parse_entitlements("chat.view:true")
        assert result == {"chat.view": True}

    def test_single_without_value(self):
        result = parse_entitlements("feature.flag")
        assert result == {"feature.flag": True}

    def test_multiple(self):
        result = parse_entitlements("chat.view:true,forms.advanced:false")
        assert result == {"chat.view": True, "forms.advanced": False}

    def test_various_boolean_representations(self):
        assert parse_entitlements("f1:true") == {"f1": True}
        assert parse_entitlements("f2:false") == {"f2": False}
        assert parse_entitlements("f3:1") == {"f3": True}
        assert parse_entitlements("f4:0") == {"f4": False}
        assert parse_entitlements("f5:yes") == {"f5": True}
        assert parse_entitlements("f6:no") == {"f6": False}
        assert parse_entitlements("f7:on") == {"f7": True}
        assert parse_entitlements("f8:off") == {"f8": False}


class TestMergeWithPersona:
    def test_override_plan(self):
        base = PERSONAS["free_user"]
        merged = merge_with_persona(base, plan="pro")

        assert merged.plan == "pro"
        assert merged.roles == base.roles  # Unchanged
        assert merged.entitlements == base.entitlements  # Unchanged

    def test_override_roles(self):
        base = PERSONAS["free_user"]
        merged = merge_with_persona(base, roles=["admin"])

        assert merged.plan == base.plan
        assert merged.roles == ["admin"]
        assert merged.entitlements == base.entitlements

    def test_merge_entitlements(self):
        base = PERSONAS["free_user"]
        merged = merge_with_persona(base, entitlements={"new.feature": True})

        assert "new.feature" in merged.entitlements
        assert merged.entitlements["new.feature"] is True
        # Original entitlements preserved
        assert merged.entitlements["forms.submit"] is True


class TestExportAndLoad:
    def test_round_trip(self):
        context = SimulationContext(
            plan="enterprise",
            roles=["admin"],
            org_id="org_test",
            user_id="user_123",
            entitlements={"feature": True},
        )

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = Path(f.name)

        try:
            export_simulation(context, path)
            loaded = load_simulation(path)

            assert loaded is not None
            assert loaded.plan == "enterprise"
            assert loaded.roles == ["admin"]
            assert loaded.entitlements == {"feature": True}
        finally:
            path.unlink()

    def test_load_nonexistent(self):
        path = Path("/nonexistent/simulation.json")
        result = load_simulation(path)
        assert result is None

    def test_load_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{invalid json")
            path = Path(f.name)

        try:
            result = load_simulation(path)
            assert result is None
        finally:
            path.unlink()

"""Entitlements simulator for testing different user personas.

Allows developers and QA to simulate different user/org/plan combinations
without modifying backend data.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence


@dataclass
class SimulationContext:
    """Defines a simulation context with user/org/plan attributes."""

    plan: str
    roles: list[str]
    org_id: str
    user_id: str
    entitlements: dict[str, bool]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SimulationContext:
        """Create context from dictionary."""
        return cls(
            plan=data.get("plan", "free"),
            roles=data.get("roles", ["member"]),
            org_id=data.get("org_id", "org_simulated"),
            user_id=data.get("user_id", "user_simulated"),
            entitlements=data.get("entitlements", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "plan": self.plan,
            "roles": self.roles,
            "org_id": self.org_id,
            "user_id": self.user_id,
            "entitlements": self.entitlements,
        }


# Predefined personas for quick simulation
PERSONAS: dict[str, SimulationContext] = {
    "free_user": SimulationContext(
        plan="free",
        roles=["member"],
        org_id="org_free_demo",
        user_id="user_free_001",
        entitlements={
            "home.view": True,
            "content.view": True,
            "forms.view": True,
            "forms.submit": True,
            "chat.view": False,
            "chat.reply": False,
            "forms.advanced": False,
        },
    ),
    "pro_admin": SimulationContext(
        plan="pro",
        roles=["admin", "member"],
        org_id="org_pro_demo",
        user_id="user_pro_admin_001",
        entitlements={
            "home.view": True,
            "content.view": True,
            "forms.view": True,
            "forms.submit": True,
            "chat.view": True,
            "chat.reply": True,
            "forms.advanced": True,
            "settings.view": True,
        },
    ),
    "pro_member": SimulationContext(
        plan="pro",
        roles=["member"],
        org_id="org_pro_demo",
        user_id="user_pro_member_001",
        entitlements={
            "home.view": True,
            "content.view": True,
            "forms.view": True,
            "forms.submit": True,
            "chat.view": True,
            "chat.reply": False,
            "forms.advanced": True,
            "settings.view": True,
        },
    ),
    "enterprise_member": SimulationContext(
        plan="enterprise",
        roles=["member"],
        org_id="org_enterprise_demo",
        user_id="user_ent_member_001",
        entitlements={
            "home.view": True,
            "content.view": True,
            "forms.view": True,
            "forms.submit": True,
            "chat.view": True,
            "chat.reply": True,
            "forms.advanced": True,
            "analytics.view": True,
            "analytics.export": True,
            "settings.view": True,
        },
    ),
    "guest": SimulationContext(
        plan="free",
        roles=[],
        org_id="",
        user_id="user_guest",
        entitlements={
            "home.view": False,
            "content.view": False,
            "forms.view": False,
            "forms.submit": False,
            "chat.view": False,
            "settings.view": False,
        },
    ),
    "beta_user": SimulationContext(
        plan="pro",
        roles=["member", "beta_tester"],
        org_id="org_beta_demo",
        user_id="user_beta_001",
        entitlements={
            "home.view": True,
            "content.view": True,
            "forms.view": True,
            "forms.submit": True,
            "chat.view": True,
            "chat.reply": True,
            "forms.advanced": True,
            "beta.feature": True,
            "beta.experimental": True,
            "settings.view": True,
        },
    ),
}


def parse_entitlements(entitlements_str: str) -> dict[str, bool]:
    """Parse entitlements string into dictionary.

    Args:
        entitlements_str: Comma-separated key:value pairs (e.g., "chat.view:true,forms.advanced:true")

    Returns:
        Dictionary of feature key to boolean value
    """
    result: dict[str, bool] = {}
    if not entitlements_str:
        return result

    for item in entitlements_str.split(","):
        if ":" in item:
            key, value = item.split(":", 1)
            result[key.strip()] = value.lower() in ("true", "1", "yes", "on")
        else:
            result[item.strip()] = True

    return result


def print_simulation(context: SimulationContext) -> None:
    """Print simulation context in a readable format."""
    print("\n" + "=" * 50)
    print("Simulation Context")
    print("=" * 50)
    print(f"Plan:      {context.plan}")
    print(f"Roles:     {', '.join(context.roles)}")
    print(f"Org ID:    {context.org_id}")
    print(f"User ID:   {context.user_id}")
    print()
    print("Effective Entitlements:")
    print("-" * 50)

    # Sort and display
    for key in sorted(context.entitlements.keys()):
        value = context.entitlements[key]
        status = "✓" if value else "✗"
        print(f"  [{status}] {key}: {value}")

    print("=" * 50)


def merge_with_persona(
    base_persona: SimulationContext,
    plan: str | None = None,
    roles: list[str] | None = None,
    org_id: str | None = None,
    entitlements: dict[str, bool] | None = None,
) -> SimulationContext:
    """Merge custom values with a base persona.

    Args:
        base_persona: Base persona to start from
        plan: Override plan
        roles: Override roles
        org_id: Override org_id
        entitlements: Additional/overridden entitlements

    Returns:
        New SimulationContext with merged values
    """
    result = SimulationContext(
        plan=plan if plan else base_persona.plan,
        roles=roles if roles else list(base_persona.roles),
        org_id=org_id if org_id else base_persona.org_id,
        user_id=base_persona.user_id,
        entitlements=dict(base_persona.entitlements),
    )

    if entitlements:
        result.entitlements.update(entitlements)

    return result


def export_simulation(context: SimulationContext, output_path: Path) -> None:
    """Export simulation context to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(context.to_dict(), f, indent=2)


def load_simulation(input_path: Path) -> SimulationContext | None:
    """Load simulation context from JSON file."""
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return SimulationContext.from_dict(data)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def main(argv: Sequence[str] | None = None) -> int:
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        prog="simulate",
        description="Simulate different user personas for testing feature gates",
    )
    parser.add_argument(
        "--list-personas",
        action="store_true",
        help="List available personas",
    )
    parser.add_argument(
        "--persona",
        choices=list(PERSONAS.keys()),
        help="Use a predefined persona",
    )
    parser.add_argument(
        "--plan",
        choices=["free", "pro", "enterprise"],
        help="Plan tier",
    )
    parser.add_argument(
        "--roles",
        help="Comma-separated roles (e.g., 'admin,member')",
    )
    parser.add_argument(
        "--org-id",
        help="Organization ID",
    )
    parser.add_argument(
        "--entitlements",
        help="Comma-separated key:value pairs (e.g., 'chat.view:true,forms.advanced:false')",
    )
    parser.add_argument(
        "--export",
        type=Path,
        help="Export simulation to JSON file",
    )
    parser.add_argument(
        "--load",
        type=Path,
        help="Load simulation from JSON file",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format",
    )

    args = parser.parse_args(argv)

    # List personas
    if args.list_personas:
        print("\nAvailable Personas:")
        print("-" * 40)
        for name, context in PERSONAS.items():
            print(f"\n{name}:")
            print(f"  Plan: {context.plan}")
            print(f"  Roles: {', '.join(context.roles)}")
            print(f"  Features: {len(context.entitlements)}")
        return 0

    # Load from file if specified
    if args.load:
        context = load_simulation(args.load)
        if context is None:
            print(f"Error: Could not load simulation from {args.load}", file=sys.stderr)
            return 1
    elif args.persona:
        # Start with base persona
        base = PERSONAS[args.persona]
        custom_roles = args.roles.split(",") if args.roles else None
        custom_entitlements = parse_entitlements(args.entitlements) if args.entitlements else None
        context = merge_with_persona(
            base,
            plan=args.plan,
            roles=custom_roles,
            org_id=args.org_id,
            entitlements=custom_entitlements,
        )
    else:
        # Build custom context
        context = SimulationContext(
            plan=args.plan or "free",
            roles=args.roles.split(",") if args.roles else ["member"],
            org_id=args.org_id or "org_custom",
            user_id="user_simulated",
            entitlements=parse_entitlements(args.entitlements) if args.entitlements else {},
        )

    # Export if requested
    if args.export:
        export_simulation(context, args.export)
        if args.format == "text":
            print(f"Simulation exported to: {args.export}")

    # Print simulation
    if args.format == "json":
        print(json.dumps(context.to_dict(), indent=2))
    else:
        print_simulation(context)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

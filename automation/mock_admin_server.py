"""Mock Admin Dashboard API server for testing.

This module provides a simple mock server that simulates the Admin Dashboard API
for local testing and CI pipeline validation.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any


# Sample feature flags for testing environments
MOCK_FEATURES = {
    "dev": [
        {"key": "chat.view", "value": True, "rules": []},
        {"key": "chat.reply", "value": True, "rules": []},
        {"key": "forms.submit", "value": True, "rules": []},
        {"key": "forms.advanced", "value": True, "rules": []},
        {"key": "debug.gates", "value": True, "rules": []},
    ],
    "stg": [
        {"key": "chat.view", "value": True, "rules": [{"if": {"percent": 50}, "value": True}]},
        {"key": "chat.reply", "value": False, "rules": [{"if": {"role": "admin"}, "value": True}]},
        {"key": "forms.submit", "value": True, "rules": []},
        {"key": "forms.advanced", "value": False, "rules": []},
        {"key": "debug.gates", "value": False, "rules": []},
    ],
    "prod": [
        {"key": "chat.view", "value": False, "rules": [{"if": {"plan": "pro"}, "value": True}]},
        {"key": "chat.reply", "value": False, "rules": [{"if": {"plan": "pro", "role": "admin"}, "value": True}]},
        {"key": "forms.submit", "value": True, "rules": []},
        {"key": "forms.advanced", "value": False, "rules": [{"if": {"plan": "pro"}, "value": True}]},
    ],
}


def generate_export(environment: str) -> dict[str, Any]:
    """Generate config export for an environment."""
    return {
        "environment": environment,
        "exportedAt": datetime.now(timezone.utc).isoformat(),
        "features": MOCK_FEATURES.get(environment, []),
        "signature": None,  # Would be computed on real server
    }


class MockAdminHandler(BaseHTTPRequestHandler):
    """Handler for mock Admin Dashboard API requests."""
    
    VALID_API_KEY = "test-api-key-12345"
    
    def _send_json(self, data: dict[str, Any], status: int = 200) -> None:
        """Send JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def _send_error(self, message: str, status: int = 400) -> None:
        """Send error response."""
        self._send_json({"error": message}, status)
    
    def _check_auth(self) -> bool:
        """Check if request has valid authentication."""
        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            self._send_error("Missing or invalid Authorization header", 401)
            return False
        
        token = auth_header[7:]  # Remove "Bearer " prefix
        if token != self.VALID_API_KEY:
            self._send_error("Invalid API key", 401)
            return False
        
        return True
    
    def do_GET(self) -> None:
        """Handle GET requests."""
        # Health check endpoint
        if self.path == "/health":
            self._send_json({"status": "ok", "service": "mock-admin-api"})
            return
        
        # Feature flags endpoint
        if self.path.startswith("/v1/config/"):
            if not self._check_auth():
                return
            
            environment = self.path.split("/")[-1]
            valid_envs = {"dev", "stg", "prod"}
            
            if environment not in valid_envs:
                self._send_error(
                    f"Invalid environment. Must be one of: {', '.join(valid_envs)}",
                    400
                )
                return
            
            self._send_json(generate_export(environment))
            return
        
        # List all environments
        if self.path == "/v1/config":
            if not self._check_auth():
                return
            
            self._send_json({
                "environments": ["dev", "stg", "prod"],
                "version": "1.0.0",
            })
            return
        
        self._send_error(f"Not found: {self.path}", 404)
    
    def do_POST(self) -> None:
        """Handle POST requests."""
        self._send_error("Method not allowed", 405)
    
    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default logging unless VERBOSE is set."""
        if os.environ.get("VERBOSE"):
            super().log_message(format, *args)


def run_server(port: int = 8765) -> None:
    """Run the mock Admin Dashboard API server.
    
    Args:
        port: Port to listen on (default: 8765)
    """
    server = HTTPServer(("127.0.0.1", port), MockAdminHandler)
    print(f"Mock Admin Dashboard API running on http://localhost:{port}")
    print(f"API Key: {MockAdminHandler.VALID_API_KEY}")
    print("Available environments: dev, stg, prod")
    print("Press Ctrl+C to stop")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Mock Admin Dashboard API Server")
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port to listen on (default: 8765)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        os.environ["VERBOSE"] = "1"
    
    run_server(args.port)

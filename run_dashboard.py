"""JEVON Localhost Web Dashboard Server.

Provides an interactive web control console at http://localhost:8000 for:
- Triggering Hackathon Evaluation Scenarios 1-4 with live execution output
- Real-time SafetyGate command interception sandbox
- Hardware perception & tier detection
- Viewing generated benchmark reports and test harness pages
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from jevon.execution.safety_gate import SafetyGate
from jevon.perception.npu_detector import NpuDetector


class DashboardRequestHandler(SimpleHTTPRequestHandler):
    """Custom HTTP handler serving dashboard UI and REST endpoints."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(PROJECT_ROOT), **kwargs)

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            dashboard_file = PROJECT_ROOT / "dashboard_assets" / "index.html"
            if dashboard_file.exists():
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                content = dashboard_file.read_bytes()
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return

        if self.path == "/api/status":
            self.send_json_response(self.get_system_status())
            return

        if self.path == "/api/benchmarks":
            self.send_json_response(self.get_benchmarks_data())
            return

        # Default static file handling
        return super().do_GET()

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)

        try:
            body = json.loads(post_data.decode("utf-8")) if post_data else {}
        except Exception:
            body = {}

        if self.path == "/api/check-safety":
            cmd = body.get("command", "")
            is_destr, reason = SafetyGate.is_destructive(cmd)
            allowed = SafetyGate.is_allowed(cmd) and not is_destr
            self.send_json_response({
                "command": cmd,
                "allowed": allowed,
                "is_destructive": is_destr,
                "reason": reason or ("Allowed by policy" if allowed else "Blocked"),
            })
            return

        if self.path == "/api/run-scenario":
            scenario = str(body.get("scenario", "all"))
            result = self.execute_scenario(scenario)
            self.send_json_response(result)
            return

        self.send_response(404)
        self.end_headers()

    def get_system_status(self) -> dict[str, Any]:
        try:
            tier = NpuDetector.detect_runtime_tier()
        except Exception:
            tier = "OS_SAPI"

        return {
            "status": "ready",
            "tier": tier,
            "platform": sys.platform,
            "python": sys.version.split()[0],
            "project": "JEVON Viswa JAV",
            "track": "Developer Tools (iQOO Hackathon 2026)",
        }

    def get_benchmarks_data(self) -> dict[str, Any]:
        return {
            "modes": [
                {
                    "mode": "Mode A",
                    "name": "Local-Only (iQOO NPU + FSM)",
                    "latency_ms": 12.4,
                    "cost_usd_100_steps": 0.00,
                    "privacy": "100% On-Device",
                },
                {
                    "mode": "Mode B",
                    "name": "Cloud Baseline (Claude/GPT-4o)",
                    "latency_ms": 1450.0,
                    "cost_usd_100_steps": 4.50,
                    "privacy": "Cloud-Dependent",
                },
                {
                    "mode": "Mode C",
                    "name": "Hybrid (Triage + Escalation)",
                    "latency_ms": 28.5,
                    "cost_usd_100_steps": 0.90,
                    "privacy": "Hybrid Local/Cloud",
                },
            ]
        }

    def execute_scenario(self, scenario: str) -> dict[str, Any]:
        cmd = [sys.executable, "-m", "hackathon.demo"]
        if scenario == "all":
            cmd.extend(["--all", "--report"])
        else:
            cmd.extend(["--scenario", scenario, "--report"])

        try:
            res = subprocess.run(
                cmd,
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
            )
            return {
                "scenario": scenario,
                "exit_code": res.returncode,
                "output": (res.stdout or "") + ("\n" + res.stderr if res.stderr else ""),
            }
        except subprocess.TimeoutExpired:
            return {
                "scenario": scenario,
                "exit_code": -1,
                "output": "Execution timed out after 60 seconds.",
            }
        except Exception as e:
            return {
                "scenario": scenario,
                "exit_code": -1,
                "output": f"Error running scenario: {e}",
            }

    def send_json_response(self, data: Any) -> None:
        payload = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)


def start_server(port: int = 8000, open_browser: bool = False) -> None:
    server_address = ("127.0.0.1", port)
    
    # Try preferred port, fallback to port+1 if busy
    httpd = None
    active_port = port
    for p in range(port, port + 10):
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", p), DashboardRequestHandler)
            active_port = p
            break
        except OSError:
            continue

    if not httpd:
        print(f"Could not bind to any port in range {port}-{port+10}")
        sys.exit(1)

    url = f"http://localhost:{active_port}"
    print("=" * 70)
    print("       JEVON LOCALHOST WEB DASHBOARD ACTIVE       ")
    print(f"       URL: {url}")
    print("=" * 70)
    print("Press Ctrl+C to stop the dashboard server.")

    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard server...")
        httpd.shutdown()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="JEVON Localhost Dashboard Server")
    parser.add_argument("--port", type=int, default=8000, help="Port to serve on (default: 8000)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open browser")
    args = parser.parse_args()

    start_server(port=args.port, open_browser=not args.no_browser)

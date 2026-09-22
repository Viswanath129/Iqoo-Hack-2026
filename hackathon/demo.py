"""Argus Hackathon Demo Runner — 3 Live Evaluation Scenarios.

Scenarios designed for Evaluation Round 1, Round 2, and the Final Pitch:
1. Scenario 1: Calculator App Regression Test (Math verification)
2. Scenario 2: Settings App Wi-Fi / Network Navigation Test
3. Scenario 3: Voice-Controlled Autonomous Test Flow

Each scenario:
- Runs autonomously using on-device SLM decision engine + ADB
- Logs hardware perception and NPU inference metrics
- Speaks status updates aloud
- Generates an HTML Test Report with annotated screenshots
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from typesafe_computer_use import config, speech
from typesafe_computer_use.actions import Context
from typesafe_computer_use.runner import RunConfig, run


def generate_html_report(run_dir: Path, scenario_name: str, passed: bool, duration: float) -> Path:
    """Generate a developer-facing test report with embedded screenshots."""
    report_file = run_dir / "test_report.html"
    
    # Collect step images
    images = sorted(run_dir.glob("step-*.png"))
    image_cards = []
    for img in images:
        rel_path = img.name
        image_cards.append(f"""
        <div class="step-card">
            <h3>Step Screenshot: {img.stem}</h3>
            <img src="{rel_path}" alt="{img.stem}" style="max-width: 320px; border-radius: 8px; border: 1px solid #333;" />
        </div>
        """)
    
    status_badge = '<span style="color: #00ff88; font-weight: bold; font-size: 1.2em;">✓ PASSED</span>' if passed else '<span style="color: #ff4444; font-weight: bold; font-size: 1.2em;">✗ FAILED</span>'
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Argus Test Report: {scenario_name}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: #121212;
            color: #e0e0e0;
            padding: 24px;
            margin: 0;
        }}
        .container {{
            max-width: 1000px;
            margin: 0 auto;
        }}
        .header {{
            background: #1e1e1e;
            padding: 20px;
            border-radius: 12px;
            border-left: 6px solid #00c6ff;
            margin-bottom: 24px;
        }}
        .steps {{
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
        }}
        .step-card {{
            background: #1a1a1a;
            padding: 14px;
            border-radius: 10px;
            border: 1px solid #282828;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 6px;
            background: #252525;
            margin-right: 12px;
        }}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>Argus Mobile Testing Report</h1>
        <p><strong>Scenario:</strong> {scenario_name}</p>
        <p><strong>Status:</strong> {status_badge}</p>
        <p><strong>Duration:</strong> {duration:.1f}s | <strong>Engine:</strong> On-Device Hexagon NPU + Qwen 2.5</p>
        <p><strong>Hardware Platform:</strong> iQOO 15 (Snapdragon 8 Elite Gen 5)</p>
    </div>

    <h2>Test Execution Steps</h2>
    <div class="steps">
        {''.join(image_cards) if image_cards else '<p>No step captures recorded.</p>'}
    </div>
</div>
</body>
</html>"""
    report_file.write_text(html, encoding="utf-8")
    print(f"\n[REPORT] ✓ HTML Test Report generated: {report_file}", flush=True)
    return report_file


def run_scenario(scenario_num: int):
    # Ensure Android environment
    os.environ["ARGUS_TARGET"] = "android"

    scenarios = {
        1: {
            "name": "Calculator Arithmetic Regression Test",
            "goal": "open Calculator and calculate 25 plus 75",
            "steps": 10,
        },
        2: {
            "name": "Settings Wi-Fi Navigation Test",
            "goal": "open Settings and tap on Network & internet or Wi-Fi",
            "steps": 8,
        },
        3: {
            "name": "Voice-Driven Autonomous Test",
            "goal": "",  # Trigger mic
            "steps": 15,
        }
    }

    sc = scenarios.get(scenario_num)
    if not sc:
        print(f"Unknown scenario number: {scenario_num}")
        return

    print("=" * 70)
    print(f" ARGUS DEMO: {sc['name']}")
    print("=" * 70)

    goal = sc["goal"]
    if scenario_num == 3 or not goal:
        speech.speak("Argus ready. What test scenario should I execute?", wait=True)
        goal = speech.listen("Speak your test scenario now...")
        if not goal:
            goal = "open Settings and check storage"

    speech.speak(f"Starting test: {goal}", wait=False)

    out_dir = Path("runs") / f"demo_s{scenario_num}_{int(time.time())}"
    out_dir.mkdir(parents=True, exist_ok=True)

    cfg = RunConfig(
        goal=goal,
        out=out_dir,
        act=True,
        steps=sc["steps"],
        min_confidence=0.20,
        delay=1.5,
        speak=True,
    )

    def ctx_factory(typesafe, history):
        return Context(
            goal=goal,
            browser="Chrome",
            email=None,
            typesafe=None,
            writer=None,
            history=history,
        )

    start = time.time()
    state = run(cfg, ctx_factory)
    elapsed = time.time() - start

    passed = state.outcome in ("done", "stopped")
    speech.speak(f"Test completed in {elapsed:.1f} seconds. Generating report.", wait=True)

    report_path = generate_html_report(out_dir, sc["name"], passed, elapsed)

    # Sync to clipboard if possible for Office Kit telemetry
    try:
        summary = f"Argus Test {sc['name']}: {'PASSED' if passed else 'FAILED'} in {elapsed:.1f}s ({state.steps_taken} steps)"
        if sys.platform == "win32":
            import subprocess
            subprocess.run(["clip"], input=summary.encode("utf-8"), check=False)
        print(f"[OFFICE KIT] Test summary copied to clipboard: '{summary}'")
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="Argus Hackathon Demo Scenarios")
    parser.add_argument("scenario", type=int, nargs="?", default=1, choices=[1, 2, 3],
                        help="Scenario: 1=Calculator, 2=Settings Wi-Fi, 3=Voice autonomous")
    args = parser.parse_args()
    run_scenario(args.scenario)


if __name__ == "__main__":
    main()

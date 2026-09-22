"""Unified E2E Test Runner for JEVON.

Supports CLI flags:
    --all: Runs all tiers (Tiers 1-4)
    --tier 1: Feature coverage tests (>=100 tests)
    --tier 2: Boundary & corner case tests (>=100 tests)
    --tier 3: Pairwise combination tests (>=20 tests)
    --tier 4: Real-world developer workload scenarios (>=6 scenarios)
    --json: Output structured results as JSON
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
import traceback
import unittest
from typing import Any


class TimingTestResult(unittest.TestResult):
    """TestResult collector recording microsecond timing and structured diagnostics."""

    def __init__(self, tier_name: str) -> None:
        super().__init__()
        self.tier_name = tier_name
        self.records: list[dict[str, Any]] = []
        self._test_start_ns: int = 0

    def startTest(self, test: unittest.TestCase) -> None:
        super().startTest(test)
        self._test_start_ns = time.perf_counter_ns()

    def addSuccess(self, test: unittest.TestCase) -> None:
        super().addSuccess(test)
        elapsed_us = (time.perf_counter_ns() - self._test_start_ns) // 1000
        self.records.append({
            "test_id": test.id(),
            "tier": self.tier_name,
            "status": "PASS",
            "duration_us": elapsed_us,
            "duration_ms": round(elapsed_us / 1000.0, 3),
            "error": None,
        })

    def addFailure(self, test: unittest.TestCase, err: Any) -> None:
        super().addFailure(test, err)
        elapsed_us = (time.perf_counter_ns() - self._test_start_ns) // 1000
        formatted_err = "".join(traceback.format_exception(*err))
        self.records.append({
            "test_id": test.id(),
            "tier": self.tier_name,
            "status": "FAIL",
            "duration_us": elapsed_us,
            "duration_ms": round(elapsed_us / 1000.0, 3),
            "error": formatted_err,
        })

    def addError(self, test: unittest.TestCase, err: Any) -> None:
        super().addError(test, err)
        elapsed_us = (time.perf_counter_ns() - self._test_start_ns) // 1000
        formatted_err = "".join(traceback.format_exception(*err))
        self.records.append({
            "test_id": test.id(),
            "tier": self.tier_name,
            "status": "ERROR",
            "duration_us": elapsed_us,
            "duration_ms": round(elapsed_us / 1000.0, 3),
            "error": formatted_err,
        })

    def addSkip(self, test: unittest.TestCase, reason: str) -> None:
        super().addSkip(test, reason)
        elapsed_us = (time.perf_counter_ns() - self._test_start_ns) // 1000
        self.records.append({
            "test_id": test.id(),
            "tier": self.tier_name,
            "status": "SKIP",
            "duration_us": elapsed_us,
            "duration_ms": round(elapsed_us / 1000.0, 3),
            "error": reason,
        })


def discover_and_run_tier(tier_key: str, tier_dir: Path, verbose: bool = False) -> tuple[TimingTestResult, int]:
    """Discover tests in a given tier directory and execute them with microsecond timing."""
    loader = unittest.TestLoader()
    result = TimingTestResult(tier_name=tier_key)

    if not tier_dir.exists():
        return result, 0

    suite = loader.discover(
        start_dir=str(tier_dir),
        pattern="test_*.py",
        top_level_dir=str(tier_dir.parent.parent),
    )

    t0 = time.perf_counter_ns()
    suite.run(result)
    tier_duration_us = (time.perf_counter_ns() - t0) // 1000

    if verbose:
        for r in result.records:
            status_symbol = "✓" if r["status"] == "PASS" else "✗"
            print(f"  [{status_symbol}] {r['test_id']} ({r['duration_ms']}ms)")

    return result, tier_duration_us


def main() -> int:
    parser = argparse.ArgumentParser(description="JEVON E2E Unified Test Runner")
    parser.add_argument("--all", action="store_true", help="Run all E2E test tiers (1, 2, 3, 4)")
    parser.add_argument("--tier", type=int, choices=[1, 2, 3, 4], help="Run a specific test tier")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print verbose test results")
    parser.add_argument("--output", type=str, default="e2e_results.json", help="Path to save JSON results")

    args = parser.parse_args()

    # Default to --all if neither --all nor --tier is specified
    if not args.all and args.tier is None:
        args.all = True

    e2e_root = Path(__file__).parent.resolve()
    project_root = e2e_root.parent.resolve()

    tier_map = {
        1: ("Tier 1 (Feature)", e2e_root / "tier1_feature"),
        2: ("Tier 2 (Boundary)", e2e_root / "tier2_boundary"),
        3: ("Tier 3 (Combination)", e2e_root / "tier3_combination"),
        4: ("Tier 4 (Application)", e2e_root / "tier4_application"),
    }

    selected_tiers: list[int] = [1, 2, 3, 4] if args.all else [args.tier]

    all_records: list[dict[str, Any]] = []
    tier_summaries: dict[str, Any] = {}
    total_passed = 0
    total_failed = 0
    total_errors = 0
    total_skipped = 0
    overall_start_ns = time.perf_counter_ns()

    if not args.json:
        print("\n=======================================================")
        print("           JEVON MULTI-TIER E2E TEST RUNNER            ")
        print("=======================================================")

    for t_num in selected_tiers:
        t_name, t_dir = tier_map[t_num]
        if not args.json:
            print(f"\n>> Running {t_name} from {t_dir.name}/ ...")

        res, dur_us = discover_and_run_tier(t_name, t_dir, verbose=args.verbose)
        all_records.extend(res.records)

        passed = sum(1 for r in res.records if r["status"] == "PASS")
        failed = sum(1 for r in res.records if r["status"] == "FAIL")
        errors = sum(1 for r in res.records if r["status"] == "ERROR")
        skipped = sum(1 for r in res.records if r["status"] == "SKIP")

        total_passed += passed
        total_failed += failed
        total_errors += errors
        total_skipped += skipped

        tier_summaries[f"tier_{t_num}"] = {
            "name": t_name,
            "total": len(res.records),
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "skipped": skipped,
            "duration_ms": round(dur_us / 1000.0, 3),
        }

        if not args.json:
            status_text = "PASSED" if failed == 0 and errors == 0 else "FAILED"
            print(f"   Result: {status_text} | Total: {len(res.records)} | Passed: {passed} | Failed: {failed} | Errors: {errors} | Duration: {round(dur_us / 1000.0, 2)}ms")

    overall_duration_us = (time.perf_counter_ns() - overall_start_ns) // 1000
    overall_duration_ms = round(overall_duration_us / 1000.0, 2)
    overall_passed = (total_failed == 0 and total_errors == 0)

    report_payload = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "PASSED" if overall_passed else "FAILED",
        "total_tests": len(all_records),
        "passed": total_passed,
        "failed": total_failed,
        "errors": total_errors,
        "skipped": total_skipped,
        "duration_ms": overall_duration_ms,
        "tier_summaries": tier_summaries,
        "test_results": all_records,
    }

    # Save output JSON
    output_path = project_root / args.output
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report_payload, f, indent=2)
    except Exception as e:
        print(f"Warning: Failed to write {output_path}: {e}", file=sys.stderr)

    if args.json:
        print(json.dumps(report_payload, indent=2))
    else:
        print("\n=======================================================")
        print(f"OVERALL SUMMARY: {'PASSED' if overall_passed else 'FAILED'}")
        print(f"Total Tests Executed: {len(all_records)}")
        print(f"Passed: {total_passed} | Failed: {total_failed} | Errors: {total_errors} | Skipped: {total_skipped}")
        print(f"Total Duration: {overall_duration_ms}ms")
        print(f"Results written to: {output_path}")
        print("=======================================================\n")

    return 0 if overall_passed else 1


if __name__ == "__main__":
    sys.exit(main())

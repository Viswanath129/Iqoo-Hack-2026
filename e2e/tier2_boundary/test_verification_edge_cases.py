"""Tier 2 Boundary Tests: Verification Edge Cases, Closed Loop & Benchmarks (Features 14, 15, 19, 20).

Covers:
- Feature 14: VerificationEngine (5 boundary tests)
- Feature 15: Closed-Loop Cycle (5 boundary tests)
- Feature 19: Micro-Benchmark Telemetry (5 boundary tests)
- Feature 20: Comparative Benchmark Suite (5 boundary tests)
Total: 20 tests.
"""

from __future__ import annotations

import time
import unittest

from e2e.stubs import (
    ComparativeBenchmark,
    MicroBenchmarkMetrics,
    VerificationEngine,
)
from jevon.decision.actions import DeveloperAction
from jevon.decision.local_provider import LocalDecisionProvider
from jevon.decision.provider import StateObservation
from jevon.truth_first.state import TruthFirstState

# ===========================================================================
# Feature 14 Boundary Cases: VerificationEngine
# ===========================================================================

class TestFeature14VerificationBoundaries(unittest.TestCase):
    """Boundary conditions for independent verification."""

    def setUp(self) -> None:
        self.verifier = VerificationEngine()

    def test_b14_verifier_empty_output_with_exit_zero(self) -> None:
        outcome = self.verifier.verify(exit_code=0, stdout="", stderr="")
        self.assertTrue(outcome.passed)
        self.assertTrue(outcome.checks["exit_code_zero"])

    def test_b14_verifier_exit_zero_but_error_still_in_output(self) -> None:
        # Exit code 0, but previous error is still present in output -> verification must FAIL
        prev_err = "NameError: foo"
        outcome = self.verifier.verify(
            exit_code=0,
            stdout="Running... NameError: foo occurred earlier but caught.",
            stderr="",
            previous_error=prev_err,
        )
        self.assertFalse(outcome.passed)
        self.assertFalse(outcome.checks["error_eliminated"])

    def test_b14_verifier_ast_empty_file(self) -> None:
        ok, err = self.verifier.verify_ast_syntax("")
        self.assertTrue(ok)
        self.assertIsNone(err)

    def test_b14_verifier_ast_whitespace_only(self) -> None:
        ok, err = self.verifier.verify_ast_syntax("   \n\n\t  \n")
        self.assertTrue(ok)
        self.assertIsNone(err)

    def test_b14_verifier_regex_multiline_output(self) -> None:
        output = "=== test session starts ===\nLine 1\nLine 2\n5 passed, 1 warning\n"
        self.assertTrue(self.verifier.verify_regex(output, r"\d+ passed"))


# ===========================================================================
# Feature 15 Boundary Cases: Closed-Loop Cycle
# ===========================================================================

class TestFeature15ClosedLoopBoundaries(unittest.TestCase):
    """Boundary conditions for closed feedback loop state advancement."""

    def test_b15_closed_loop_empty_state_cycle_zero(self) -> None:
        state = TruthFirstState()
        self.assertEqual(state.cycle_index, 0)
        self.assertEqual(len(state.decisions), 0)

    def test_b15_closed_loop_large_cycle_count(self) -> None:
        state = TruthFirstState()
        for i in range(1000):
            state.cycle_index += 1
            state.record_decision(f"action_{i % 8}")
        self.assertEqual(state.cycle_index, 1000)
        self.assertEqual(len(state.decisions), 1000)

    def test_b15_closed_loop_missing_recent_error_and_active_file(self) -> None:
        provider = LocalDecisionProvider()
        state = TruthFirstState()
        obs = StateObservation(active_file=None, recent_error=None, compiler_exit_code=None)
        dec = provider.decide(state, obs)
        self.assertEqual(dec.action, DeveloperAction.RERUN_BUILD)

    def test_b15_closed_loop_rapid_state_mutation(self) -> None:
        state = TruthFirstState()
        for i in range(50):
            state.add_fact(f"fact_{i}")
            state.add_constraint(f"constraint_{i}")
        self.assertEqual(len(state.facts), 50)
        self.assertEqual(len(state.constraints), 50)

    def test_b15_closed_loop_duplicate_failure_signatures_window(self) -> None:
        state = TruthFirstState()
        state.record_failure_signature("sig_A")
        # Asking for window=5 when only 1 signature exists must return False without crashing
        self.assertFalse(state.detect_repeated_failure(window=5))


# ===========================================================================
# Feature 19 Boundary Cases: Micro-Benchmark Telemetry
# ===========================================================================

class TestFeature19MicroBenchmarkBoundaries(unittest.TestCase):
    """Boundary conditions for nanosecond micro-benchmarks."""

    def test_b19_micro_benchmark_all_stages_zero(self) -> None:
        metrics = MicroBenchmarkMetrics()
        self.assertEqual(metrics.total_latency_ns, 0)
        self.assertEqual(metrics.total_latency_ms, 0.0)

    def test_b19_micro_benchmark_single_large_stage(self) -> None:
        metrics = MicroBenchmarkMetrics(action_exec_ns=10_000_000_000)  # 10s
        self.assertEqual(metrics.total_latency_ms, 10000.0)

    def test_b19_micro_benchmark_latency_precision_no_float_rounding_loss(self) -> None:
        metrics = MicroBenchmarkMetrics(
            perception_ns=123_456,
            local_inference_ns=654_321,
        )
        self.assertEqual(metrics.total_latency_ns, 777_777)

    def test_b19_micro_benchmark_measurement_overhead_sub_microsecond(self) -> None:
        t0 = time.perf_counter_ns()
        t1 = time.perf_counter_ns()
        self.assertLess(t1 - t0, 50_000)  # Under 50 microseconds

    def test_b19_micro_benchmark_dataclass_defaults(self) -> None:
        m = MicroBenchmarkMetrics()
        self.assertEqual(m.perception_ns, 0)
        self.assertEqual(m.bridge_out_ns, 0)
        self.assertEqual(m.verification_ns, 0)


# ===========================================================================
# Feature 20 Boundary Cases: Comparative Benchmark Suite
# ===========================================================================

class TestFeature20ComparativeBenchmarkBoundaries(unittest.TestCase):
    """Boundary conditions for comparative benchmark calculations."""

    def test_b20_benchmark_zero_steps_cost(self) -> None:
        self.assertEqual(ComparativeBenchmark.calculate_cost("Mode A", 0), 0.0)
        self.assertEqual(ComparativeBenchmark.calculate_cost("Mode B", 0), 0.0)
        self.assertEqual(ComparativeBenchmark.calculate_cost("Mode C", 0), 0.0)

    def test_b20_benchmark_large_step_cost(self) -> None:
        # 1,000,000 steps
        cost_a = ComparativeBenchmark.calculate_cost("Mode A", 1_000_000)
        cost_b = ComparativeBenchmark.calculate_cost("Mode B", 1_000_000)
        cost_c = ComparativeBenchmark.calculate_cost("Mode C", 1_000_000)
        self.assertEqual(cost_a, 0.0)
        self.assertEqual(cost_b, 45_000.0)
        self.assertEqual(cost_c, 9_000.0)

    def test_b20_benchmark_comparison_table_headers(self) -> None:
        table = ComparativeBenchmark.generate_comparison_table(steps=10)
        lines = table.splitlines()
        self.assertIn("| Mode |", lines[0])
        self.assertIn("Mode A", lines[2])
        self.assertIn("Mode B", lines[3])
        self.assertIn("Mode C", lines[4])

    def test_b20_benchmark_mode_keys_exact(self) -> None:
        keys = set(ComparativeBenchmark.MODES.keys())
        self.assertEqual(keys, {"Mode A", "Mode B", "Mode C"})

    def test_b20_benchmark_cost_monotonicity(self) -> None:
        steps = 500
        cost_a = ComparativeBenchmark.calculate_cost("Mode A", steps)
        cost_b = ComparativeBenchmark.calculate_cost("Mode B", steps)
        cost_c = ComparativeBenchmark.calculate_cost("Mode C", steps)
        self.assertGreater(cost_b, cost_c)
        self.assertGreater(cost_c, cost_a)


if __name__ == "__main__":
    unittest.main()

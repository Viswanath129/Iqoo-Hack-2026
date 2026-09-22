"""Tier 4 Scenario S6: End-to-End Comparative Benchmark Run Workflow.

Features Exercised:
- F19: Nanosecond Micro-Benchmark Latency Instrumentation
- F20: Comparative Benchmark Suite (Modes A, B, C)
"""

from __future__ import annotations

import time
import unittest

from e2e.stubs import (
    ComparativeBenchmark,
    MicroBenchmarkMetrics,
)


class TestScenarioComparativeBenchmarkFlow(unittest.TestCase):
    """Scenario S6: Execution of comparative benchmarks contrasting Local-Only, Cloud, and Hybrid."""

    def test_scenario_s6_comparative_benchmark_full_execution(self) -> None:
        # Step 1: Instrument a simulated dual-device loop round with real nanosecond timings
        t_start = time.perf_counter_ns()

        # 1. Perception
        t0 = time.perf_counter_ns()
        time.sleep(0.002)  # 2ms simulated speech/screen capture
        t_perception = time.perf_counter_ns() - t0

        # 2. Local Inference
        t0 = time.perf_counter_ns()
        time.sleep(0.003)  # 3ms rule/SLM inference
        t_local_inf = time.perf_counter_ns() - t0

        # 3. Decision
        t0 = time.perf_counter_ns()
        time.sleep(0.001)  # 1ms FSM decision evaluation
        t_decision = time.perf_counter_ns() - t0

        # 4. Bridge Out
        t0 = time.perf_counter_ns()
        time.sleep(0.0005)  # 0.5ms socket transmission
        t_bridge_out = time.perf_counter_ns() - t0

        # 5. Action Execution
        t0 = time.perf_counter_ns()
        time.sleep(0.005)  # 5ms test/build execution
        t_action_exec = time.perf_counter_ns() - t0

        # 6. Verification
        t0 = time.perf_counter_ns()
        time.sleep(0.001)  # 1ms AST/regex verification
        t_verification = time.perf_counter_ns() - t0

        # 7. Bridge In
        t0 = time.perf_counter_ns()
        time.sleep(0.0005)  # 0.5ms receipt return
        t_bridge_in = time.perf_counter_ns() - t0

        metrics = MicroBenchmarkMetrics(
            perception_ns=t_perception,
            local_inference_ns=t_local_inf,
            decision_ns=t_decision,
            bridge_out_ns=t_bridge_out,
            action_exec_ns=t_action_exec,
            verification_ns=t_verification,
            bridge_in_ns=t_bridge_in,
        )

        self.assertGreater(metrics.total_latency_ns, 0)
        self.assertGreaterEqual(metrics.total_latency_ms, 10.0)

        # Step 2: Calculate Comparative Benchmark Metrics across 100 developer steps
        steps = 100
        cost_a = ComparativeBenchmark.calculate_cost("Mode A", steps)
        cost_b = ComparativeBenchmark.calculate_cost("Mode B", steps)
        cost_c = ComparativeBenchmark.calculate_cost("Mode C", steps)

        # Mode A (Local-Only) must be $0.00
        self.assertEqual(cost_a, 0.0)
        # Mode B (Cloud Baseline) is 100 * $0.045 = $4.50
        self.assertAlmostEqual(cost_b, 4.50, places=2)
        # Mode C (Hybrid) is 100 * $0.009 = $0.90
        self.assertAlmostEqual(cost_c, 0.90, places=2)

        # Step 3: Render Empirical Latency & Cost Table
        table_output = ComparativeBenchmark.generate_comparison_table(steps=steps)
        self.assertIn("Mode A", table_output)
        self.assertIn("Mode B", table_output)
        self.assertIn("Mode C", table_output)
        self.assertIn("$0.000", table_output)
        self.assertIn("$4.500", table_output)
        self.assertIn("$0.900", table_output)
        self.assertIn("100% On-Device", table_output)


if __name__ == "__main__":
    unittest.main()

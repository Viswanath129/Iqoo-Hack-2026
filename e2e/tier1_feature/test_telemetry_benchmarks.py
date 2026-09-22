"""Tier 1 Feature Tests: Nanosecond Micro-Benchmarks & Comparative Suite (Features 19, 20).

Covers:
- Feature 19: Nanosecond Micro-Benchmark Latency Instrumentation (5 tests)
- Feature 20: Comparative Benchmark Suite (Modes A, B, C) (5 tests)
Total: 10 tests.
"""

from __future__ import annotations

import time
import unittest

from e2e.stubs import (
    ComparativeBenchmark,
    MicroBenchmarkMetrics,
)

# ===========================================================================
# Feature 19: Nanosecond Micro-Benchmark Latency Instrumentation (R6)
# ===========================================================================

class TestFeature19MicroBenchmarks(unittest.TestCase):
    """Validates Feature 19: Nanosecond timing across all 7 pipeline stages."""

    def test_f19_nanosecond_micro_benchmark_total_sum(self) -> None:
        metrics = MicroBenchmarkMetrics(
            perception_ns=1_000_000,       # 1ms
            local_inference_ns=3_000_000,  # 3ms
            decision_ns=500_000,           # 0.5ms
            bridge_out_ns=200_000,         # 0.2ms
            action_exec_ns=25_000_000,     # 25ms
            verification_ns=4_000_000,     # 4ms
            bridge_in_ns=300_000,          # 0.3ms
        )
        self.assertEqual(metrics.total_latency_ns, 34_000_000)

    def test_f19_nanosecond_to_millisecond_conversion(self) -> None:
        metrics = MicroBenchmarkMetrics(
            decision_ns=15_500_000,
        )
        self.assertEqual(metrics.total_latency_ms, 15.5)

    def test_f19_stopwatch_positive_monotonicity(self) -> None:
        t0 = time.perf_counter_ns()
        time.sleep(0.005)  # 5ms
        elapsed_ns = time.perf_counter_ns() - t0
        self.assertGreater(elapsed_ns, 0)
        self.assertGreaterEqual(elapsed_ns, 4_000_000)  # at least ~4ms

    def test_f19_all_seven_stages_instrumented(self) -> None:
        metrics = MicroBenchmarkMetrics()
        expected_fields = [
            "perception_ns",
            "local_inference_ns",
            "decision_ns",
            "bridge_out_ns",
            "action_exec_ns",
            "verification_ns",
            "bridge_in_ns",
        ]
        for field_name in expected_fields:
            self.assertTrue(hasattr(metrics, field_name), f"Missing field {field_name}")

    def test_f19_sub_millisecond_precision_record(self) -> None:
        t0 = time.perf_counter_ns()
        # Fast in-memory operation
        _ = [x * x for x in range(500)]
        elapsed_ns = time.perf_counter_ns() - t0
        self.assertLess(elapsed_ns, 10_000_000)  # Less than 10ms


# ===========================================================================
# Feature 20: Comparative Benchmark Suite (Modes A, B, C) (R6)
# ===========================================================================

class TestFeature20ComparativeBenchmarks(unittest.TestCase):
    """Validates Feature 20: Comparative benchmarks across Local (A), Cloud (B), and Hybrid (C)."""

    def test_f20_comparative_benchmark_modes_exist(self) -> None:
        modes = ComparativeBenchmark.MODES
        self.assertIn("Mode A", modes)
        self.assertIn("Mode B", modes)
        self.assertIn("Mode C", modes)

    def test_f20_mode_a_local_only_zero_cloud_cost(self) -> None:
        cost_100 = ComparativeBenchmark.calculate_cost("Mode A", 100)
        cost_1000 = ComparativeBenchmark.calculate_cost("Mode A", 1000)
        self.assertEqual(cost_100, 0.0)
        self.assertEqual(cost_1000, 0.0)

    def test_f20_mode_b_cloud_cost_calculation(self) -> None:
        cost_100 = ComparativeBenchmark.calculate_cost("Mode B", 100)
        # 100 steps * $0.045 = $4.50
        self.assertAlmostEqual(cost_100, 4.50, places=2)

    def test_f20_comparative_table_generation(self) -> None:
        table_md = ComparativeBenchmark.generate_comparison_table(steps=50)
        self.assertIn("| Mode | Name | Latency (avg) | Cloud Cost (50 steps) | Privacy / Offline |", table_md)
        self.assertIn("Mode A", table_md)
        self.assertIn("Mode B", table_md)
        self.assertIn("Mode C", table_md)
        self.assertIn("100% On-Device", table_md)

    def test_f20_comparative_benchmark_invalid_mode_raises(self) -> None:
        with self.assertRaises(ValueError):
            ComparativeBenchmark.calculate_cost("Mode D", 10)


if __name__ == "__main__":
    unittest.main()

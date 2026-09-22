"""Nanosecond-precision stopwatch and micro-benchmark metrics for JEVON."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MicroBenchmarkMetrics:
    """Nanosecond-precision latency stopwatch for all 7 loop stages."""

    perception_ns: int = 0
    local_inference_ns: int = 0
    decision_ns: int = 0
    bridge_out_ns: int = 0
    action_exec_ns: int = 0
    verification_ns: int = 0
    bridge_in_ns: int = 0

    @property
    def total_latency_ns(self) -> int:
        return (
            self.perception_ns
            + self.local_inference_ns
            + self.decision_ns
            + self.bridge_out_ns
            + self.action_exec_ns
            + self.verification_ns
            + self.bridge_in_ns
        )

    @property
    def total_latency_ms(self) -> float:
        return self.total_latency_ns / 1_000_000.0

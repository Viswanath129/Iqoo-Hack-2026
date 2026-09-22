# Telemetry & Benchmarks

## Overview

JEVON instruments every pipeline stage with nanosecond-precision timing and provides a comparative benchmark suite contrasting three operating modes.

**Source**: [`jevon/telemetry/`](../jevon/telemetry/)

---

## `MicroBenchmarkMetrics`

**Source**: [`jevon/telemetry/metrics.py`](../jevon/telemetry/metrics.py)

Nanosecond-precision stopwatch capturing latency across **7 pipeline stages**:

```python
@dataclass
class MicroBenchmarkMetrics:
    perception_ns: int = 0        # Screen capture + OCR + UIA tree
    local_inference_ns: int = 0   # SLM model inference
    decision_ns: int = 0          # Decision provider evaluation
    bridge_out_ns: int = 0        # Phone → Laptop bridge send
    action_exec_ns: int = 0       # Subprocess execution
    verification_ns: int = 0      # Independent verification checks
    bridge_in_ns: int = 0         # Laptop → Phone receipt send
```

### Properties

| Property | Returns | Formula |
|:---|:---|:---|
| `total_latency_ns` | `int` | Sum of all 7 stages (nanoseconds) |
| `total_latency_ms` | `float` | `total_latency_ns / 1,000,000` (milliseconds) |

### Usage in the Orchestrator

```python
step_metrics = MicroBenchmarkMetrics()

# Stage 1: Decision
t0 = time.perf_counter_ns()
decision = provider.decide(state, obs)
step_metrics.decision_ns = time.perf_counter_ns() - t0

# Stage 2: Bridge send
step_metrics.bridge_out_ns = bridge.send_command(cmd)

# Stage 3: Execution
t0 = time.perf_counter_ns()
receipt = executor.execute(cmd_str)
step_metrics.action_exec_ns = time.perf_counter_ns() - t0

# Stage 4: Verification
t0 = time.perf_counter_ns()
verif = verifier.verify(...)
step_metrics.verification_ns = time.perf_counter_ns() - t0

# Total
print(f"Step latency: {step_metrics.total_latency_ms:.2f}ms")
```

---

## `ComparativeBenchmark`

**Source**: [`jevon/telemetry/benchmark.py`](../jevon/telemetry/benchmark.py)

Compares three operating modes across latency, cost, and privacy dimensions.

### Mode Definitions

| Mode | Name | Description |
|:---|:---|:---|
| **Mode A** | Local-Only (iQOO NPU + Local FSM) | Zero-cloud: on-device SLM + rule heuristics |
| **Mode B** | Cloud Baseline (Claude/GPT-4o) | Traditional cloud LLM roundtrip |
| **Mode C** | Hybrid (Local Triage + Cloud Escalation) | Local for routine, cloud for ambiguous |

### Benchmark Data

| Mode | Average Latency | Cloud Cost/Step | Cost per 100 Steps | Privacy |
|:---|:---:|:---:|:---:|:---|
| **Mode A** | **12.4ms** | **$0.000** | **$0.00** | 100% On-Device |
| **Mode B** | 1,450ms | $0.045 | $4.50 | Cloud-Dependent |
| **Mode C** | 28.5ms | $0.009 | $0.90 | Hybrid |

### Key Comparisons

| Metric | Mode A vs Mode B |
|:---|:---|
| **Speed** | **117× faster** |
| **Cost** | **∞× cheaper** ($0.00 vs $4.50/100 steps) |
| **Privacy** | Complete on-device vs cloud-dependent |
| **Offline** | Works without internet vs requires internet |

### Cost Calculator

```python
ComparativeBenchmark.calculate_cost("Mode A", 100)  # $0.00
ComparativeBenchmark.calculate_cost("Mode B", 100)  # $4.50
ComparativeBenchmark.calculate_cost("Mode C", 100)  # $0.90
```

### Comparison Table Generator

```python
print(ComparativeBenchmark.generate_comparison_table(steps=100))
```

Output:
```
| Mode | Name | Latency (avg) | Cloud Cost (100 steps) | Privacy / Offline |
|---|---|---|---|---|
| Mode A | Local-Only (iQOO NPU + Local FSM) | 12.4ms | $0.000 | 100% On-Device |
| Mode B | Cloud Baseline (Claude/GPT-4o) | 1450.0ms | $4.500 | Cloud-Dependent |
| Mode C | Hybrid (Local Triage + Cloud Escalation) | 28.5ms | $0.900 | Hybrid |
```

---

## Bridge Latency Records

The `OfficeKitBridge` maintains a running list of latency measurements:

```python
bridge.latency_records
# [
#   {"type": "send_observation", "latency_ns": 45230},
#   {"type": "send_command",     "latency_ns": 38100},
#   {"type": "send_receipt",     "latency_ns": 41500},
#   ...
# ]
```

---

## Pipeline Stage Breakdown

```
┌────────────────────┬──────────────────────────────────────────────┐
│ Stage              │ What's Measured                              │
├────────────────────┼──────────────────────────────────────────────┤
│ 1. Perception      │ Screen capture + OCR + UIA tree extraction  │
│ 2. Local Inference  │ SLM model forward pass (if used)           │
│ 3. Decision         │ Provider.decide() evaluation               │
│ 4. Bridge Out       │ Phone → Laptop command transmission        │
│ 5. Action Execution │ Subprocess run with timeout                │
│ 6. Verification     │ Exit code + regex + AST + error checks     │
│ 7. Bridge In        │ Laptop → Phone receipt transmission        │
└────────────────────┴──────────────────────────────────────────────┘
```

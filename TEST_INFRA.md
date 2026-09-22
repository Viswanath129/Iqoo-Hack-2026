# E2E Test Infra: JEVON (On-Device Developer Decision Engine)

## Test Philosophy
- **Requirement-Driven & Opaque-Box**: Tests are derived strictly from `ORIGINAL_REQUEST.md` (R1-R6) and public user-facing specifications, completely decoupled from implementation internals.
- **Progressive Testability**: Verification mechanisms do not require features more complex than what they verify. Early tiers yield pass/fail signals independently.
- **Strict Integrity**: Zero dummy implementations, zero hardcoded test outputs, zero simulated hardware claims.
- **Methodology**: Systematic 4-Tier design (Category-Partition + Boundary Value Analysis + Pairwise Combinatorial + Real-World Workload Scenarios) plus Tier 5 Adversarial Hardening.

---

## Feature Inventory Coverage Matrix

| # | Feature | Requirement | Tier 1 (Feature) | Tier 2 (Boundary) | Tier 3 (Pairwise) |
|---|---------|-------------|:----------------:|:-----------------:|:-----------------:|
| 1 | `DecisionProvider` Interface & Polymorphism | R1 | 5 tests | 5 tests | ✓ |
| 2 | Bounded Action Space ($\le 8$ Actions) | R1 | 5 tests | 5 tests | ✓ |
| 3 | `LocalDecisionProvider` Offline (0 API Keys) | R1 | 5 tests | 5 tests | ✓ |
| 4 | `TypeSafeJevProvider` Cloud Fallback | R1 | 5 tests | 5 tests | ✓ |
| 5 | `SafetyFallback` Interceptor ($C < 0.60$ / Loops) | R1 | 5 tests | 5 tests | ✓ |
| 6 | Typed Decisions (Confidence & Probability Sum = 1.0) | R1 | 5 tests | 5 tests | ✓ |
| 7 | Truth-First State Model (7 Pillars) | R3 | 5 tests | 5 tests | ✓ |
| 8 | Telemetry Schemas (`StateObservation`, `DecisionCommand`, `ActionReceipt`) | R2 | 5 tests | 5 tests | ✓ |
| 9 | `OfficeKitBridge` Bi-Directional Protocol | R2 | 5 tests | 5 tests | ✓ |
| 10 | Tri-Transport Layer (ADB Tunnel, Socket, Local IPC) | R2 | 5 tests | 5 tests | ✓ |
| 11 | `LaptopActionExecutor` Adaptation & Process Isolation | R4 | 5 tests | 5 tests | ✓ |
| 12 | Safety Failsafes (Mouse Corner 10px, 30s Timeout, Allowlist) | R4 | 5 tests | 5 tests | ✓ |
| 13 | `SafetyGate` Destructive Action Blocking | R4 | 5 tests | 5 tests | ✓ |
| 14 | `VerificationEngine` Independent Validation (No Self-Cert) | R5 | 5 tests | 5 tests | ✓ |
| 15 | Closed-Loop Cycle (`STATE -> DECISION -> ... -> NEXT STATE`) | R5 | 5 tests | 5 tests | ✓ |
| 16 | Honest NPU Runtime Detection (4 Tiers, Zero Fake Claims) | R3 | 5 tests | 5 tests | ✓ |
| 17 | Whisper STT Perception Pipeline | R3 | 5 tests | 5 tests | ✓ |
| 18 | TTS Audio Feedback & Terminal Error Extractor | R3 | 5 tests | 5 tests | ✓ |
| 19 | Nanosecond Micro-Benchmark Latency Instrumentation | R6 | 5 tests | 5 tests | ✓ |
| 20 | Comparative Benchmark Suite (Modes A, B, C) | R6 | 5 tests | 5 tests | ✓ |

---

## Test Architecture

### 1. Test Directory Layout
```
B:\projects\viswa_jav\e2e\
├── runner.py                     # Unified test runner orchestrating all tiers
├── fixtures/                     # Test fixtures (broken build, test failures, git repo)
│   ├── broken_syntax/            # Fixture with syntax error
│   ├── broken_test/              # Fixture with failing unit test
│   ├── clean_project/            # Fixture with passing build
│   └── destructive_commands/     # Dangerous commands requiring SafetyGate
├── tier1_feature/                # Tier 1 tests: Individual feature validation (>= 100 tests)
│   ├── test_decision_engine.py
│   ├── test_bridge_transports.py
│   ├── test_laptop_execution.py
│   ├── test_perception_npu.py
│   ├── test_verification_engine.py
│   └── test_telemetry_benchmarks.py
├── tier2_boundary/               # Tier 2 tests: Boundary & corner cases (>= 100 tests)
│   ├── test_action_bounds.py
│   ├── test_network_timeouts.py
│   ├── test_extreme_inputs.py
│   ├── test_safety_violations.py
│   └── test_verification_edge_cases.py
├── tier3_combination/            # Tier 3 tests: Pairwise feature interactions (>= 20 tests)
│   ├── test_bridge_with_decision.py
│   ├── test_decision_with_executor.py
│   ├── test_executor_with_verifier.py
│   └── test_truth_state_with_bridge.py
├── tier4_application/            # Tier 4 tests: Real-world developer workloads (>= 6 scenarios)
│   ├── test_scenario_syntax_fix.py
│   ├── test_scenario_failing_test_debug.py
│   ├── test_scenario_destructive_gate.py
│   ├── test_scenario_offline_decision_loop.py
│   ├── test_scenario_bridge_disconnect_recovery.py
│   └── test_scenario_full_dual_device_flow.py
└── tier5_adversarial/            # Tier 5 tests: Adversarial stress testing (Challenger phase)
```

### 2. Invocation & Execution Semantics
- Run full suite:
  ```powershell
  python e2e/runner.py --all
  ```
- Run specific tier:
  ```powershell
  python e2e/runner.py --tier 1
  python e2e/runner.py --tier 2
  python e2e/runner.py --tier 3
  python e2e/runner.py --tier 4
  ```
- Pass criteria: Exit code 0, 100% test pass, zero regressions, JSON output generated at `e2e_results.json`.

---

## Real-World Application Scenarios (Tier 4)

| # | Scenario | Features Exercised | Complexity | Target Outcome |
|---|----------|--------------------|------------|----------------|
| S1 | Syntax Error Auto-Diagnosis & Fix | F1, F2, F3, F7, F8, F11, F14, F15 | High | Detects Python SyntaxError, inspects error line, applies patch, verifier confirms clean syntax and exit code 0 |
| S2 | Failing Unit Test Debug Loop | F1, F2, F3, F6, F11, F14, F15 | High | Test fails with assertion error, engine triggers `inspect_error`, runs targeted test, verifies pass regex |
| S3 | Destructive Action Interception | F1, F12, F13 | Medium | Command `git reset --hard` or `rm -rf` dispatched; `SafetyGate` halts execution, requests confirmation, rejects unauthorized execution |
| S4 | Full Offline Dual-Device Roundtrip | F1, F3, F6, F7, F8, F9, F10 | Very High | StateObservation sent from laptop via Local IPC to phone intelligence; LocalDecisionProvider decides offline; DecisionCommand returned and executed; ActionReceipt received and verified |
| S5 | Network Dropout & Reconnection Recovery | F8, F9, F10, F12 | Medium | Simulates socket disconnection mid-loop; bridge re-establishes connection and resumes without state corruption |
| S6 | End-to-End Comparative Benchmark Run | F19, F20 | Medium | Runs benchmark CLI across Mode A, Mode B, Mode C, verifies latency table output and cost calculations |

---

## Coverage Thresholds
- **Tier 1 (Feature)**: $\ge 5$ test cases per feature $\times$ 20 features = **$\ge 100$ test cases**
- **Tier 2 (Boundary & Corner)**: $\ge 5$ test cases per feature $\times$ 20 features = **$\ge 100$ test cases**
- **Tier 3 (Pairwise Interactions)**: $\ge 20$ pairwise combinatorial test cases
- **Tier 4 (Real-World Scenarios)**: $\ge 6$ comprehensive developer scenarios
- **Total Minimum Target: $\ge 226$ E2E test cases**
- **Existing Unit Tests Target: Exactly 170 passed (0 regressions)**

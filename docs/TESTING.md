# Testing Infrastructure

## Overview

JEVON maintains a comprehensive dual-track testing strategy:

| Track | Location | Tests | Status |
|:---|:---|:---:|:---:|
| **Unit Tests** | `tests/` | 170 | ✅ All Passing |
| **E2E Test Suite** | `e2e/` | 226 | ✅ All Passing |
| **Total** | — | **396** | ✅ |

---

## Unit Tests (170 Tests)

### Location: `tests/`

### Test Files

| File | Focus | Est. Tests |
|:---|:---|:---:|
| `test_actions.py` | Desktop action handlers (click, type, scroll, launch) | ~15 |
| `test_adversarial_m1.py` | Adversarial stress tests for decision engine | ~20 |
| `test_android.py` | Android ADB adapter | ~10 |
| `test_answer.py` | Answer format and parsing | ~10 |
| `test_ax.py` | Accessibility tree processing | ~15 |
| `test_challenger_m1_truth_first.py` | Truth-First state challenger tests | ~20 |
| `test_config_and_writer.py` | Configuration and writer | ~5 |
| `test_dates.py` | Date utility functions | ~5 |
| `test_decide.py` | Decision logic (cloud mode) | ~10 |
| `test_jevon_decision.py` | JEVON decision engine (actions, providers, safety) | ~25 |
| `test_jevon_truth_first.py` | Truth-First state model | ~15 |
| `test_local_decide.py` | Local decision heuristic | ~5 |
| `test_ocr_cache.py` | OCR tile caching | ~15 |
| `test_perception.py` | Perception pipeline | ~10 |
| `test_slm_decide.py` | SLM decision engine | ~10 |
| `test_speech.py` | Speech module | ~5 |
| `test_timing.py` | Timing utilities | ~5 |
| `test_windows.py` | Windows backend | ~10 |

### Running Unit Tests

```powershell
# Run all unit tests
uv run pytest tests/

# Run with verbose output
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_jevon_decision.py

# Run excluding interactive tests (no mouse/keyboard)
uv run pytest tests/ -m "not interactive"

# Run with short summary
uv run pytest tests/ -q
```

---

## E2E Test Suite (226 Tests)

### Location: `e2e/`

### Test Tiers

| Tier | Focus | Tests | Duration | Description |
|:---|:---|:---:|:---:|:---|
| **Tier 1 — Feature** | Feature isolation & contracts | 100 | ~1.57s | ≥5 tests per feature across 20 features |
| **Tier 2 — Boundary** | Extreme inputs & edge cases | 100 | ~2.96s | Timeouts, safety violations, invalid inputs |
| **Tier 3 — Combination** | Cross-module interactions | 20 | ~2.44s | Pairwise module integration tests |
| **Tier 4 — Application** | Real-world scenarios | 6 | ~1.29s | End-to-end developer workflows |
| **Total** | — | **226** | **~8.3s** | — |

### Tier 1: Feature Coverage (100 Tests)

| File | Features Covered | Tests |
|:---|:---|:---:|
| `test_decision_engine.py` | Features 1–6 (Decision providers, actions, safety) | 30 |
| `test_bridge_transports.py` | Features 8–10 (IPC, Socket, ADB transports) | 15 |
| `test_laptop_execution.py` | Features 11–13 (Executor, SafetyGate, allowlist) | 15 |
| `test_perception_npu.py` | Features 7, 16–18 (NPU, Whisper, TTS, extractor) | 20 |
| `test_verification_engine.py` | Features 14–15 (Verification, closed loop) | 10 |
| `test_telemetry_benchmarks.py` | Features 19–20 (Metrics, benchmarks) | 10 |

### Tier 2: Boundary Cases (100 Tests)

| File | Focus | Tests |
|:---|:---|:---:|
| `test_action_bounds.py` | Decision engine boundaries (NaN, Inf, empty inputs) | 30 |
| `test_network_timeouts.py` | Transport timeouts and disconnections | 15 |
| `test_extreme_inputs.py` | Extreme perception inputs (empty screens, huge text) | 20 |
| `test_safety_violations.py` | Safety gate edge cases (all 7 destructive patterns) | 15 |
| `test_verification_edge_cases.py` | Verification with malformed inputs | 20 |

### Tier 3: Cross-Module Combinations (20 Tests)

| File | Modules Combined | Tests |
|:---|:---|:---:|
| `test_bridge_with_decision.py` | Bridge + DecisionProvider | 5 |
| `test_decision_with_executor.py` | DecisionProvider + LaptopActionExecutor | 5 |
| `test_executor_with_verifier.py` | LaptopActionExecutor + VerificationEngine | 5 |
| `test_truth_state_with_bridge.py` | TruthFirstState + OfficeKitBridge | 5 |

### Tier 4: Application Scenarios (6 Tests)

| # | Scenario | What It Tests |
|:---|:---|:---|
| **S1** | Syntax Error Auto-Diagnosis & Fix | Full decision chain: `INSPECT_ERROR` → `INSPECT_FILE` → `APPLY_FIX` → `RUN_TEST` → `RERUN_BUILD` → `DONE` |
| **S2** | Failing Unit Test Debug Loop | `AssertionError` detection, targeted test, semantic patch, pass regex verification |
| **S3** | Destructive Action Interception | `git reset --hard`, `rm -rf`, `.env` access — all `BLOCKED_BY_SAFETY` |
| **S4** | Full Offline Dual-Device Roundtrip | IPC bridge, LocalDecisionProvider with 0 cloud keys, verified receipt |
| **S5** | Network Dropout & Recovery | Socket disconnect, `ConnectionError` handling, reconnection, resumed flow |
| **S6** | Comparative Benchmark Execution | 7-stage nanosecond instrumentation, Mode A/B/C cost calculation |

---

## Running E2E Tests

### Unified E2E Runner

```powershell
# Run all tiers
python e2e/runner.py --all

# Run specific tier
python e2e/runner.py --tier 1
python e2e/runner.py --tier 2
python e2e/runner.py --tier 3
python e2e/runner.py --tier 4

# Verbose output (test-by-test)
python e2e/runner.py --all -v

# JSON output (also saves to e2e_results.json)
python e2e/runner.py --all --json
```

### Via Pytest Directly

```powershell
uv run pytest e2e/tier1_feature
uv run pytest e2e/tier2_boundary
uv run pytest e2e/tier3_combination
uv run pytest e2e/tier4_application
```

---

## Test Fixtures

Located in `e2e/fixtures/`:

| Fixture | Purpose |
|:---|:---|
| `broken_syntax/` | Python project containing a `SyntaxError` |
| `broken_test/` | Project with a failing unit test assertion |
| `clean_project/` | Clean project with 100% passing tests |
| `destructive_commands/` | Destructive action payloads for SafetyGate testing |

---

## Test Infrastructure Files

| File | Purpose |
|:---|:---|
| `e2e/runner.py` | Unified test runner with microsecond timing and structured JSON reporting |
| `e2e/stubs.py` | Protocol contract stubs and dynamic binding utilities |
| `tests/conftest.py` | Shared pytest configuration and fixture definitions |
| `e2e_results.json` | Persisted JSON results from the last E2E run |

---

## Test Integrity Guarantees

1. **Zero hardcoded results** — All tests execute genuine assertions against real fixtures and models
2. **Zero facade tests** — All edge cases, failure states, and safety boundaries are strictly exercised
3. **Zero regressions** — All 170 original unit tests continue to pass
4. **Independent verification** — Tests validate verification engine output, not decision engine claims
5. **Reproducible fixtures** — Deterministic test data, no network or hardware dependencies

---

## Linting

```powershell
# Check for lint errors
uv run ruff check .

# Auto-format code
uv run ruff format .
```

Configuration in `pyproject.toml`:
- Line length: 130
- Target: Python 3.12
- Rules: E, F, I, B, UP, SIM, RUF
- Ignored: E501 (line length handled by formatter)

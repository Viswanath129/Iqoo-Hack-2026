# Original User Request

## Initial Request — 2026-09-22T15:21:54Z

<USER_REQUEST>
Transform viswa_jav into JEVON (On-Device Developer Decision Engine), an on-device developer decision-and-execution layer for the iQOO Hackathon 2026 Developer Tools track that drives a verified Build/Test/Debug loop from an iQOO phone across an Office Kit bridge to a Windows laptop.

Working directory: B:\projects\viswa_jav
Integrity mode: development

## Requirements

### R1. Core Decision Engine & Bounded Action Space
Implement a pluggable decision provider abstraction (`DecisionProvider`) featuring a primary on-device `LocalDecisionProvider` (operating completely offline with zero cloud API keys), an optional `TypeSafeJevProvider`, and a deterministic `SafetyFallback`. The engine must output typed decisions (`Decision { action, confidence, metadata }`) across a bounded, mutually exclusive candidate action set (e.g. `inspect_error`, `inspect_file`, `run_targeted_test`, `rerun_build`, `inspect_recent_change`, `apply_fix`, `request_confirmation`, `done`).

### R2. Dual-Device Architecture & Office Kit Bridge
Separate the system into an on-device intelligence center (running on the iQOO phone / Android environment) and an execution target (Windows/ARM64 developer machine). Implement a bi-directional, latency-instrumented bridge layer (`OfficeKitBridge`) supporting both Office Kit network sockets/USB-debugging channels and local IPC fallback, exchanging structured telemetry (`StateObservation`, `DecisionCommand`, `ActionReceipt`).

### R3. On-Device AI Perception & Voice Pipeline
Deploy local perception and multimodal intent processing on the phone layer: on-device Whisper STT utilizing Qualcomm Snapdragon NPU acceleration where runtime-supported, on-device TTS feedback, local terminal/code snippet state extraction, and truth-first state tracking (`GOAL`, `CONSTRAINTS`, `FACTS`, `DECISIONS`, `EVIDENCE`, `OPEN_QUESTIONS`, `FAILED_APPROACHES`).

### R4. Deterministic Laptop Action Execution
Adapt existing Windows automation (`windows.py`, `actions.py`, `uiautomation`, Win32 `SendInput`, `subprocess`) to execute the laptop actions dispatched by the phone. Maintain failsafe bounds: action allowlist, emergency mouse-corner stop, timeout per step, and hard-stop on low confidence or repeated identical failure states.

### R5. Objective Verification & Feedback Loop
Build an independent verification module (`verification/`) that validates whether a decided developer action succeeded (compiler exit code, test pass/fail regex, state diff, git status) without self-certification. The outcome feeds back into the phone's decision core to advance the loop: `STATE → DECISION → ACTION → OBSERVATION → VERIFICATION → NEXT STATE`.

### R6. Real-Time Telemetry & Benchmark Suite
Instrument every phase with real micro-benchmarks: perception latency, local inference latency, decision latency, bridge latency, action execution latency, and verification latency. Include a comparative benchmark suite contrasting (A) local-only mode, (B) cloud baseline, and (C) hybrid mode with recorded metrics.

## Acceptance Criteria

### Core Decision & Bounded Actions
- [x] `DecisionProvider` interface implemented with `LocalDecisionProvider` functioning offline with zero API keys.
- [x] Action space restricted to <=8 bounded, mutually exclusive developer actions.
- [x] Decisions output typed confidence scores and probability distributions.

### Bridge & Office Kit
- [x] Bi-directional protocol implemented and verified with simulated or live Office Kit socket transport.
- [x] End-to-end round trip (State -> Phone Decision -> Laptop Action -> Verified Receipt) executes reliably.

### Developer Workflow (Build/Test/Debug MVP)
- [x] Fully automated diagnosis and targeted test/build execution demonstrated on a reproducible failed build fixture.
- [x] Destructive actions (`git reset --hard`, file deletion, credential access) blocked by `SafetyGate` until confirmed.

### Verification & Truth-First Tracking
- [x] Independent verification logic asserts process exit codes and error elimination, halting on unrecovered failures.
- [x] Truth-First state model records and logs facts, hypotheses, and evidence at each step.

### Benchmarking & Honesty
- [x] Benchmark CLI produces empirical latency tables for all pipeline stages.
- [x] No unmeasured or simulated NPU/hardware claims in outputs or documentation.
- [x] Existing 170 unit tests pass without regression.
</USER_REQUEST>

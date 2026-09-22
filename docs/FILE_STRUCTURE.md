# File Structure

## Complete Project Tree

```
Iqoo-Hack-2026/
│
├── typesafe_computer_use/                   # Desktop Automation Engine (22 files)
│   ├── __init__.py                          # Package initialization
│   ├── __main__.py                          # Module entry point
│   ├── cli.py                               # CLI: clicker & clicker-inspect commands
│   ├── platform_adapter.py                  # Dynamic OS dispatch: Windows ↔ macOS ↔ Android
│   ├── windows.py                           # Win32 SendInput, UIAutomation tree, DPI capture, WinRT OCR
│   ├── macos.py                             # macOS Quartz, AXUIElement, AppleScript, Vision OCR
│   ├── android.py                           # ADB touch/key/text input, screencap, UI hierarchy dump
│   ├── actions.py                           # Action handlers: click, type, scroll, launch, browser, media
│   ├── decide.py                            # Local decision heuristic (decide_local) — keyword/intent matching
│   ├── slm_decide.py                        # Multi-backend SLM runner (ONNX GenAI → GGUF → REST → heuristic)
│   ├── perception.py                        # Screen capture, OCR merge, control indexing, reading order
│   ├── ocr.py                               # WinRT hardware OCR with tile-level change cache
│   ├── speech.py                            # TTS (WinRT SpeechSynthesizer / SAPI / macOS say) & STT
│   ├── whisper_npu.py                       # Qualcomm NPU Whisper STT with QNN EP and REST fallback
│   ├── runner.py                            # Main execution loop coordinator
│   ├── writer.py                            # Claude free-text composition for typing and URL generation
│   ├── config.py                            # Configuration constants, .env loader, site catalog
│   ├── models.py                            # Data models: Screen, Item, Field, AxNode
│   ├── report.py                            # Annotated screenshot rendering and payload formatting
│   ├── timing.py                            # Timing utilities and human-readable formatting
│   └── dates.py                             # Date context generation for time-aware decisions
│
├── jevon/                                   # JEVON Decision Engine (30+ files)
│   ├── __init__.py                          # Public API exports (25 symbols)
│   ├── __main__.py                          # Module entry point
│   ├── cli.py                               # JEVON-specific CLI interface
│   ├── loop.py                              # ClosedLoopOrchestrator: STATE→DECISION→ACTION→VERIFY loop
│   │
│   ├── decision/                            # Core Decision Engine (R1)
│   │   ├── __init__.py                      # Decision module exports
│   │   ├── actions.py                       # 8-action DeveloperAction enum & DeveloperDecision dataclass
│   │   ├── provider.py                      # DecisionProvider ABC & StateObservation contract
│   │   ├── local_provider.py                # LocalDecisionProvider: 7-rule offline FSM
│   │   ├── jev_provider.py                  # TypeSafeJevProvider: cloud classifier + local fallback
│   │   └── safety_fallback.py               # SafetyFallback: confidence, oscillation, precondition guards
│   │
│   ├── truth_first/                         # Truth-First State Model (R3)
│   │   ├── __init__.py                      # Module exports
│   │   └── state.py                         # TruthFirstState: 7-pillar ledger, failure signatures
│   │
│   ├── bridge/                              # Office Kit Bridge (R2)
│   │   ├── __init__.py                      # Module exports
│   │   ├── protocol.py                      # DecisionCommand & ActionReceipt frozen dataclasses
│   │   ├── bridge.py                        # OfficeKitBridge: latency-instrumented coordinator
│   │   └── transports.py                    # IpcTransport, SocketTransport, AdbTunnelTransport
│   │
│   ├── execution/                           # Laptop Execution Layer (R4)
│   │   ├── __init__.py                      # Module exports
│   │   ├── executor.py                      # LaptopActionExecutor: subprocess, timeout, corner abort
│   │   ├── safety_gate.py                   # SafetyGate: 7 destructive command regex patterns
│   │   └── allowlist.py                     # ALLOWED_COMMAND_PREFIXES, ABORT_CORNER_PX, STEP_TIMEOUT
│   │
│   ├── verification/                        # Independent Verification (R5)
│   │   ├── __init__.py                      # Module exports
│   │   └── engine.py                        # VerificationEngine: exit code, regex, AST, error elimination
│   │
│   ├── perception/                          # On-Device Perception & Voice (R3)
│   │   ├── __init__.py                      # Module exports
│   │   ├── npu_detector.py                  # NpuDetector: honest 4-tier hardware probe
│   │   ├── extractor.py                     # TerminalErrorExtractor: traceback/error parsing
│   │   └── voice.py                         # Voice adapter
│   │
│   └── telemetry/                           # Benchmarking & Metrics (R6)
│       ├── __init__.py                      # Module exports
│       ├── metrics.py                       # MicroBenchmarkMetrics: 7-stage nanosecond stopwatch
│       └── benchmark.py                     # ComparativeBenchmark: Mode A/B/C comparison
│
├── tests/                                   # Unit Tests (170 tests, 19 files)
│   ├── conftest.py                          # Shared pytest fixtures and configuration
│   ├── fixtures/                            # Test fixture data
│   ├── e2e/                                 # Legacy E2E test directory
│   ├── test_actions.py                      # Desktop action handler tests
│   ├── test_adversarial_m1.py               # Adversarial stress tests
│   ├── test_android.py                      # Android ADB adapter tests
│   ├── test_answer.py                       # Answer format and parsing tests
│   ├── test_ax.py                           # Accessibility tree processing tests
│   ├── test_challenger_m1_truth_first.py    # Truth-First challenger tests
│   ├── test_config_and_writer.py            # Config and writer tests
│   ├── test_dates.py                        # Date utility tests
│   ├── test_decide.py                       # Cloud decision logic tests
│   ├── test_jevon_decision.py               # JEVON decision engine tests
│   ├── test_jevon_truth_first.py            # Truth-First state model tests
│   ├── test_local_decide.py                 # Local heuristic decision tests
│   ├── test_ocr_cache.py                    # OCR tile caching tests
│   ├── test_perception.py                   # Perception pipeline tests
│   ├── test_slm_decide.py                   # SLM decision engine tests
│   ├── test_speech.py                       # Speech module tests
│   ├── test_timing.py                       # Timing utility tests
│   └── test_windows.py                      # Windows backend tests
│
├── e2e/                                     # E2E Test Suite (226 tests)
│   ├── __init__.py                          # Package init
│   ├── runner.py                            # Unified test runner with microsecond timing
│   ├── stubs.py                             # Protocol contract stubs & dynamic binding
│   ├── fixtures/                            # Reproducible test fixtures
│   │   ├── broken_syntax/                   # Project with SyntaxError
│   │   ├── broken_test/                     # Project with failing assertion
│   │   ├── clean_project/                   # Clean passing project
│   │   └── destructive_commands/            # Destructive action payloads
│   ├── tier1_feature/                       # Tier 1: Feature coverage (100 tests)
│   │   ├── test_decision_engine.py
│   │   ├── test_bridge_transports.py
│   │   ├── test_laptop_execution.py
│   │   ├── test_perception_npu.py
│   │   ├── test_verification_engine.py
│   │   └── test_telemetry_benchmarks.py
│   ├── tier2_boundary/                      # Tier 2: Boundary cases (100 tests)
│   │   ├── test_action_bounds.py
│   │   ├── test_network_timeouts.py
│   │   ├── test_extreme_inputs.py
│   │   ├── test_safety_violations.py
│   │   └── test_verification_edge_cases.py
│   ├── tier3_combination/                   # Tier 3: Cross-module (20 tests)
│   │   ├── test_bridge_with_decision.py
│   │   ├── test_decision_with_executor.py
│   │   ├── test_executor_with_verifier.py
│   │   └── test_truth_state_with_bridge.py
│   └── tier4_application/                   # Tier 4: Real-world scenarios (6 tests)
│       ├── test_scenario_syntax_fix.py
│       ├── test_scenario_failing_test_debug.py
│       ├── test_scenario_destructive_gate.py
│       ├── test_scenario_offline_decision_loop.py
│       ├── test_scenario_bridge_disconnect_recovery.py
│       └── test_scenario_full_dual_device_flow.py
│
├── hackathon/                               # Hackathon Assets
│   ├── __init__.py                          # Package init
│   ├── pitch.md                             # 3-minute pitch script with Q&A
│   ├── demo.py                              # Live demo automation script
│   ├── download_models.py                   # SLM model downloader (GGUF/ONNX)
│   ├── setup_officekit.md                   # iQOO Office Kit setup & telemetry guide
│   └── setup_phone.sh                       # Android phone setup script
│
├── docs/                                    # Documentation & Brand Assets (18 files)
│   ├── README.md                            # Documentation index / hub & brand identity
│   ├── assets/                              # Brand identity & SVG graphics
│   │   ├── logo.svg                         # Dynamic animated SVG logo (NPU lattice & feedback loop)
│   │   └── logo-mono.svg                    # Monochrome monoline vector logo (currentColor support)
│   ├── logo.svg                             # Backwards-compatible dynamic logo
│   ├── ARCHITECTURE.md                      # System architecture & diagrams
│   ├── DECISION_ENGINE.md                   # Decision engine deep dive
│   ├── TRUTH_FIRST_LEDGER.md                # 7-pillar state model
│   ├── BRIDGE_PROTOCOL.md                   # Office Kit bridge & transports
│   ├── EXECUTION_SAFETY.md                  # Execution layer & SafetyGate
│   ├── VERIFICATION_ENGINE.md               # Independent verification
│   ├── PERCEPTION_VOICE.md                  # Perception, NPU, voice
│   ├── TELEMETRY.md                         # Benchmarking & metrics
│   ├── API_REFERENCE.md                     # Data contracts & interfaces
│   ├── CLI_REFERENCE.md                     # CLI usage guide
│   ├── SETUP_GUIDE.md                       # Installation & setup
│   ├── TESTING.md                           # Testing infrastructure
│   ├── HARDWARE_PLATFORMS.md                # Platform support matrix
│   ├── SECURITY_MODEL.md                    # 7-layer security architecture
│   ├── SPECIFICATION.md                     # Comprehensive engineering specification
│   └── FILE_STRUCTURE.md                    # This file
│
├── .github/                                 # GitHub configuration
│
├── pyproject.toml                           # Project config: deps, build, lint, test
├── uv.lock                                  # Dependency lock file
├── README.md                                # Main project README
├── PROJECT.md                               # Detailed project specification
├── PROJECT_OVERVIEW.md                      # System overview
├── ORIGINAL_REQUEST.md                      # Original requirements (R1-R6)
├── TEST_READY.md                            # E2E test readiness report
├── TEST_INFRA.md                            # Test infrastructure documentation
├── CONTRIBUTING.md                          # Contribution guidelines
├── LICENSE                                  # MIT License
├── .env.example                             # Environment variable template
├── .gitignore                               # Git ignore rules
├── run_voice.bat                            # Windows voice mode launcher
└── e2e_results.json                         # Persisted E2E test results (JSON)
```

---

## File Count Summary

| Directory | Files | Lines (est.) | Purpose |
|:---|:---:|:---:|:---|
| `typesafe_computer_use/` | 22 | ~4,500 | Desktop automation engine |
| `jevon/` | 30+ | ~2,500 | Decision engine & bridge |
| `tests/` | 19 | ~3,000 | Unit tests |
| `e2e/` | 20+ | ~2,500 | E2E tests |
| `hackathon/` | 6 | ~500 | Hackathon assets |
| `docs/` (incl. `assets/`) | 18 | ~3,200 | Documentation & brand assets |
| Root | 14 | ~1,500 | Config & docs |
| **Total** | **~130** | **~17,500** | — |

<p align="center">
  <a href="../README.md">
    <img src="assets/logo.svg" alt="JEVON Logo" width="140" height="140" />
  </a>
</p>

<h1 align="center">JEVON Documentation</h1>

<p align="center">
  <strong>From developer intent &rarr; to verified code action. Zero cloud. Zero cost. Sub-2-second latency.</strong><br />
  <em>On-Device Developer Decision Engine &middot; iQOO 15 (Snapdragon 8 Elite) &middot; iQOO Hackathon 2026</em>
</p>

<p align="center">
  <a href="assets/logo.svg"><b>🎨 Dynamic Logo</b></a> &nbsp;&bull;&nbsp;
  <a href="assets/logo-mono.svg"><b>✒️ Monochrome Logo</b></a> &nbsp;&bull;&nbsp;
  <a href="../README.md"><b>⚡ Main Repository</b></a> &nbsp;&bull;&nbsp;
  <a href="../hackathon/pitch.md"><b>🎤 Pitch Script</b></a>
</p>

---

## 📚 Documentation Index

| # | Document | Description |
|:---:|:---|:---|
| 1 | [**Architecture**](ARCHITECTURE.md) | System architecture, 4-layer design, dual-device separation, Mermaid diagrams |
| 2 | [**Decision Engine**](DECISION_ENGINE.md) | 8-action bounded space, 7-rule FSM, 3 providers, probability normalization |
| 3 | [**Truth-First Ledger**](TRUTH_FIRST_LEDGER.md) | 7-pillar immutable state model, failure signatures, oscillation detection |
| 4 | [**Bridge & Protocol**](BRIDGE_PROTOCOL.md) | Office Kit Bridge, 3 transport backends, telemetry frames |
| 5 | [**Execution & Safety**](EXECUTION_SAFETY.md) | LaptopActionExecutor, SafetyGate, destructive command blocking |
| 6 | [**Verification Engine**](VERIFICATION_ENGINE.md) | Independent verification — exit code, regex, AST, error elimination |
| 7 | [**Perception & Voice**](PERCEPTION_VOICE.md) | Screen capture, NPU detection, Whisper STT, SLM pipeline, TTS |
| 8 | [**Telemetry & Benchmarks**](TELEMETRY.md) | Nanosecond metrics, Mode A/B/C comparative benchmarks |
| 9 | [**API Reference**](API_REFERENCE.md) | All data contracts, interface definitions, serialization schemas |
| 10 | [**CLI Reference**](CLI_REFERENCE.md) | `clicker` and `clicker-inspect` usage, flags, examples |
| 11 | [**Setup Guide**](SETUP_GUIDE.md) | Installation, environment, model downloads, Office Kit pairing |
| 12 | [**Testing**](TESTING.md) | 170 unit tests, 226 E2E tests across 4 tiers, invocation guide |
| 13 | [**Hardware & Platforms**](HARDWARE_PLATFORMS.md) | Windows, macOS, Android, Snapdragon X, iQOO 15 support matrix |
| 14 | [**Security Model**](SECURITY_MODEL.md) | 7-layer defense-in-depth, privacy model, threat boundaries |
| 15 | [**File Structure**](FILE_STRUCTURE.md) | Complete annotated project tree with every file's purpose |
| 16 | [**Full Specification**](SPECIFICATION.md) | Comprehensive engineering specification, state machine, and contracts |

---

## Quick Links

- **Main README**: [`../README.md`](../README.md)
- **Original Requirements (R1–R6)**: [`../ORIGINAL_REQUEST.md`](../ORIGINAL_REQUEST.md)
- **Project Specification**: [`../PROJECT.md`](../PROJECT.md)
- **Project Overview**: [`../PROJECT_OVERVIEW.md`](../PROJECT_OVERVIEW.md)
- **Test Readiness Report**: [`../TEST_READY.md`](../TEST_READY.md)
- **E2E Test Infrastructure**: [`../TEST_INFRA.md`](../TEST_INFRA.md)
- **Hackathon Pitch Script**: [`../hackathon/pitch.md`](../hackathon/pitch.md)
- **Contributing Guide**: [`../CONTRIBUTING.md`](../CONTRIBUTING.md)
- **License**: [`../LICENSE`](../LICENSE) (MIT)
- **Repository**: [github.com/Viswanath129/Iqoo-Hack-2026](https://github.com/Viswanath129/Iqoo-Hack-2026)

---

## Executive Summary

**JEVON** transforms the developer environment into an observable, closed-loop control system. It deterministically perceives screens, makes bounded decisions, executes native OS actions, and independently verifies outcomes — all **without requiring cloud API calls**.

| Dimension | Value |
|:---|:---|
| **Zero-Cloud Intelligence** | 100% on-device decision-making via local FSM + on-device SLM (Qwen 2.5) |
| **Deterministic Actions** | Bounded 8-action space with typed probability distributions summing to 1.0 |
| **Dual-Device Architecture** | iQOO phone (intelligence) ↔ Laptop (execution) via Office Kit Bridge |
| **Sub-2-Second Latency** | ~12.4ms local decision vs. ~1,450ms cloud baseline (117× faster) |
| **$0.00 Operational Cost** | Zero API tokens, zero cloud bills, complete data privacy |
| **Multi-Platform** | Windows 11, macOS, Android (ADB), Qualcomm Snapdragon X NPU |
| **Safety-First** | 7-layer defense: mouse-corner abort, SafetyGate, step timeouts, allowlists |
| **Truth-First Auditing** | 7-pillar immutable ledger with deterministic SHA-256 failure signatures |
| **396 Tests** | 170 unit tests + 226 E2E tests across 4 tiers — all passing |

---

## 🎨 Brand Identity & Symbolism

The JEVON emblem represents the synthesis of on-device edge AI, autonomous developer control, and deterministic verification.

<p align="center">
  <table align="center" style="border: none;">
    <tr>
      <td align="center" width="50%">
        <img src="assets/logo.svg" alt="JEVON Dynamic Logo" width="160" height="160" /><br />
        <b>Dynamic Full-Color Edition</b><br />
        <code>docs/assets/logo.svg</code><br />
        <em>Animated CSS Streams &middot; Dual-Glow &middot; Dark/Light Adaptive</em>
      </td>
      <td align="center" width="50%">
        <img src="assets/logo-mono.svg" alt="JEVON Monochrome Logo" width="160" height="160" /><br />
        <b>Monochrome Vector Edition</b><br />
        <code>docs/assets/logo-mono.svg</code><br />
        <em>Monoline Geometry &middot; <code>currentColor</code> &middot; CLI & Print Ready</em>
      </td>
    </tr>
  </table>
</p>

### Visual Semantic Breakdown

```
          [ iQOO 15 Snapdragon 8 Elite ]
               (Hexagon NPU Lattice)
                        │
                        ▼
   [ Perceive ] ──▶ [ Decide ] ──▶ [ Execute ]
         ▲                               │
         └───────── [ Verify ] ◀─────────┘
              (Closed-Loop Feedback)
                        │
                        ▼
             [ Developer Intent `>_` ]
               (Stylized "J" Monogram)
```

| Visual Motif | Technical & Semantic Meaning | Color Specification |
|:---|:---|:---|
| **Stylized "J" Monogram** | Represents **JEVON** and autonomous execution. Designed with bold, confident geometric curves and rounded terminals. | Velocity Orange (`#FF3700` &rarr; `#FFA200`) |
| **Terminal Prompt (`>`)** | Nested at the core of the monogram, symbolizing direct developer intent, CLI command dispatch, and on-device code intelligence. | Cyber Cyan (`#00F2FE` &rarr; `#38BDF8`) |
| **Closed-Loop Orbital Arc** | Encompasses the mark, representing the uninterrupted autonomous control loop: **Perceive &rarr; Decide &rarr; Execute &rarr; Verify**. In the dynamic version, CSS dashes stream in real time. | Cyan &rarr; Indigo &rarr; Orange Gradient |
| **Deterministic Truth Beacon** | A minimalist glowing node anchored at the apex of the "J", representing the **7-Pillar Truth-First Ledger** and verified execution. | Pure White (`#FFFFFF`) with Cyan Aura |

### Format & Compatibility Matrix

- **Dynamic Edition (`docs/assets/logo.svg` & `docs/logo.svg`)**:
  - Pure floating vector mark with transparent background (no bulky cards or drop shadows).
  - Uses embedded SVG `<style>` with keyframe animations (`dashFlow`, `beaconBreathe`, `glowPulse`).
  - Interactive hover micro-interaction (subtle 1.035 scale with spring easing).
  - Contains `@media (prefers-color-scheme: light)` for automatic contrast adaptation on both GitHub Dark and Light themes.
  - Zero external resources or scripts — fully supported by GitHub markdown, modern browsers, and static site generators.
- **Monochrome Edition (`docs/assets/logo-mono.svg`)**:
  - Pure monoline vector silhouette with unified stroke weights.
  - Built with `var(--mono-stroke, currentColor)` to seamlessly inherit foreground colors in any UI framework, CLI terminal, or documentation generator.

---

*Document generated for iQOO Hackathon 2026 submission — September 2026*


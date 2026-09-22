# JEVON
## On-Device Developer Decision Engine

> **From developer intent to verified action.**

**Target event:** iQOO Hackathon 2026 — Hyderabad City Battle  
**Target track:** Developer Tools  
**Core thesis:** Local AI perception + structured decision-making + deterministic execution + verification  
**Core loop:** `Intent → Perceive → Decide → Execute → Verify → Update`

---

## 1. Executive Definition

JEVON is a phone-first developer control layer designed to turn real development state into bounded, executable, and verifiable actions.

Instead of stopping at a natural-language answer, JEVON is designed to close the loop:

```text
Developer Intent
      ↓
Perceive Current State
      ↓
Generate / Identify Candidate Actions
      ↓
Structured Decision
      ↓
Safety / Policy Gate
      ↓
Deterministic Execution
      ↓
Observe Result
      ↓
Verify
      ↓
Update State
      ↓
Next Decision
```

The phone is intended to be the intelligence and control surface. The laptop remains the practical execution environment for IDEs, terminals, builds, tests, Git, and desktop automation. A bridge connects the two.

---

# 2. What We Are Solving

Modern AI-assisted development can stop at **generation**: the assistant produces code, commands, or explanations, but the developer still has to interpret the response, choose what to do next, execute it, inspect the result, and determine whether the task actually progressed.

That creates a gap between:

**AI understanding** and **verified developer action**.

A second problem appears in phone-first and edge environments. Sending every small decision through a large remote model can introduce network dependence and unnecessary latency or data transfer, while a phone's local AI hardware may remain underused.

JEVON therefore targets the narrower systems problem:

> **How can AI continuously turn the current developer state into the next useful action, execute that action safely, observe the outcome, and verify whether the workflow actually progressed?**

### Problem statement

> **Developers need an AI-native control layer that converts real development state into safe, bounded, executable actions and verifies their outcomes — rather than merely returning natural-language suggestions.**

### The fundamental gap

```text
Traditional assistant

Prompt
  ↓
Model
  ↓
Text / Code
  ↓
Human interprets
  ↓
Human acts
  ↓
Human verifies
```

```text
JEVON

Developer intent
       ↓
Current state
       ↓
Structured decision
       ↓
Typed action
       ↓
Policy gate
       ↓
Deterministic execution
       ↓
Evidence
       ↓
Verification
```

---

# 3. Solution — In Two Lines

**JEVON combines on-device AI with a JEV-style structured decision layer to understand developer state and select the next executable action instead of merely generating text.**

**It executes the action through deterministic developer tools, observes the result, and feeds verified evidence back into the workflow for the next decision.**

---

# 4. Why This Is a Developer Tool

JEVON is intentionally positioned around developer workflows rather than general conversation.

The primary workflow is:

```text
CREATE / DEBUG / TEST
        ↓
UNDERSTAND STATE
        ↓
SELECT NEXT ACTION
        ↓
EXECUTE
        ↓
VERIFY
```

The initial hackathon MVP should concentrate on one workflow:

> **Diagnose and verify a failed developer build.**

Possible bounded actions include:

```text
inspect_error
inspect_file
inspect_recent_change
run_targeted_test
run_build
apply_fix
request_confirmation
done
```

Only actions that actually exist in the implementation should be documented as implemented.

---

# 5. The JEV / Structured-Decision Idea

TypeSafe presents Jev as a **System One Model** intended for fast structured decisions rather than conventional conversational output. Its public positioning describes machine-consumable decisions that can be directly used by software, including typed choices, probabilities, and confidence.

The public `typesafe-computer-use` example applies this idea to computer use:

```text
Screen state
    ↓
Deterministic perception
    ↓
Bounded action choices
    ↓
JEV decision
    ↓
Deterministic action
    ↓
New screen state
    ↓
Repeat
```

JEVON applies the same systems pattern to developer tooling.

### Important distinction

JEVON should **not** claim that TypeSafe's Jev itself runs on the Snapdragon NPU unless an actual local model and verified NPU execution path are demonstrated.

The architecture should therefore support multiple decision providers:

```text
DecisionProvider
├── LocalDecisionProvider        ← primary hackathon target
├── TypeSafeJevProvider          ← optional / experimental
└── DeterministicFallback        ← safety / degraded mode
```

---

# 6. Current Project Foundation

The existing project is already centered around a Windows/ARM64 computer-use and developer-automation engine. The current project snapshot includes concepts/modules for:

- Windows platform adaptation
- Win32 / UIAutomation
- screen capture
- OCR / local perception
- local rule/heuristic decisions
- TypeSafe/JEV integration
- deterministic keyboard/mouse or UI actions
- safety controls / emergency stop
- voice or speech integration
- Qualcomm Snapdragon / Hexagon NPU experimentation
- logging and timing

The redesign is therefore **an architectural alignment, not a greenfield rewrite**.

Existing functionality should be classified before modification:

| Status | Meaning |
|---|---|
| **KEEP** | Working and architecturally useful as-is |
| **ADAPT** | Useful but needs platform/interface changes |
| **BRIDGE** | Keep as a desktop capability exposed to the phone |
| **EXPERIMENTAL** | Keep isolated until validated |
| **PLANNED** | Target capability not yet implemented |
| **REMOVE** | Conflicting, redundant, or unsafe capability |

---

# 7. Target Architecture

JEVON should become **one system with two execution surfaces** rather than two disconnected applications.

```text
                         JEVON
                           │
              ┌────────────┴────────────┐
              │                         │
        ┌─────▼─────┐             ┌─────▼─────┐
        │ iQOO PHONE│             │  LAPTOP   │
        │ Intelligence│             │ Execution │
        └─────┬─────┘             └─────┬─────┘
              │                         │
      ┌───────┼────────┐        ┌───────┼─────────┐
      │       │        │        │       │         │
    Voice  Perception Local    IDE   Terminal   Build/Test
            /OCR      AI             Git       Debug
      │       │        │        │       │         │
      └───────┴────────┘        └───────┴─────────┘
              │                         │
              └────────── Bridge ───────┘
                         │
                         ▼
                     New State
                         │
                         ▼
                      Verify
                         │
                         ▼
                     JEVON loop
```

### Role separation

**Phone**
- local AI inference where supported
- voice / intent input
- perception and context preparation
- structured decision interface
- safety policy
- workflow state
- diagnostics

**Laptop**
- IDE
- terminal
- build tools
- tests
- Git
- desktop automation
- deeper execution where necessary

**Bridge**
- state transfer
- action requests
- results
- synchronization
- connection status

---

# 8. Four-Layer System Model

JEVON should maintain strict boundaries between four major layers.

## Layer 1 — Perception

Converts raw development/device state into structured information.

Potential inputs:

```text
Screen
OCR
UIAutomation
Voice
Compiler output
Build logs
Test results
Git state
Process state
Project metadata
```

## Layer 2 — Decision

Converts state into a bounded next action.

```text
State
  ↓
Candidate actions
  ↓
Decision provider
  ↓
Action + confidence / metadata
```

## Layer 3 — Execution

Executes only validated actions through deterministic tooling.

```text
Typed action
   ↓
Safety policy
   ↓
Executor
   ↓
IDE / terminal / Git / build / test / UI
```

## Layer 4 — Verification

Determines whether the action produced the expected state change.

```text
Execution result
      ↓
Evidence
      ↓
Verification
      ↓
SUCCESS / FAILED / UNKNOWN / WAITING
```

### Core principle

> **An action being executed is not the same as the task being successful.**

---

# 9. Phone-First Architecture for iQOO

The iQOO Hackathon 2026 is explicitly phone-first. The official guide states that the iQOO device is the build and demo surface, local/open-source models at the core earn brownie points, on-device inference targets the Snapdragon NPU, and Office Kit bridges phone and laptop.

Therefore the target is not:

```text
Laptop does everything
        ↓
Phone mirrors the laptop
```

It is:

```text
Phone performs meaningful intelligence
        ↓
Phone decides / controls
        ↓
Laptop executes developer work
        ↓
Phone receives the result
        ↓
Phone verifies / continues
```

The phone must have a meaningful role even when the laptop is temporarily unavailable.

---

# 10. Local AI Strategy

Local/open-source AI should be a **core architecture path**, not a decorative feature.

Use a capability-driven runtime:

```text
HardwareCapabilities
├── CPU
├── GPU
├── NPU
└── Supported AI runtime
```

At runtime, the application should detect what is actually available.

```text
ModelBackend
├── NPU
├── GPU
└── CPU
```

The selected backend must be visible in diagnostics.

Example:

```text
AI BACKEND: NPU
```

must only be shown when the current inference path is actually using the NPU.

Do not claim NPU acceleration without measurement or runtime evidence.

---

# 11. Phone UI Concept

JEVON should not look like a conventional chatbot.

The phone should look like a **developer control console**.

### Primary UI

```text
┌──────────────────────────────┐
│ JEVON                        │
│ Developer Control            │
├──────────────────────────────┤
│ WORKFLOW                     │
│ Build / Debug                │
│                              │
│ CURRENT STATE                │
│ BUILD FAILED                 │
│                              │
│ NEXT ACTION                  │
│ inspect_error                │
│                              │
│ CONFIDENCE                   │
│ [actual runtime value]       │
│                              │
│ SAFETY                       │
│ Allowed / Confirmation      │
│                              │
│ [ EXECUTE ]                  │
└──────────────────────────────┘
```

After execution:

```text
EXECUTING
    ↓
OBSERVING
    ↓
VERIFYING
    ↓

BUILD VERIFIED
```

Every displayed metric must come from actual runtime state.

---

# 12. Voice as a Developer Interface

Voice should be an optional high-visibility interaction mode.

Example:

> “Fix the build.”

Flow:

```text
Microphone
    ↓
Local STT where supported
    ↓
Developer intent
    ↓
Workflow state
    ↓
Decision engine
```

Voice should not be required for the core workflow. The same operation should be possible through the UI.

---

# 13. Phone ↔ Laptop Bridge

The bridge must be treated as a separate transport layer.

```text
Android
   ↓
BridgeTransport
   ↓
Windows Agent
   ↓
Developer tools
```

Use a small versioned protocol.

Example conceptual request:

```json
{
  "protocolVersion": 1,
  "requestId": "...",
  "action": "run_targeted_test",
  "target": "...",
  "parameters": {}
}
```

Example conceptual result:

```json
{
  "requestId": "...",
  "status": "completed",
  "evidence": {},
  "verification": "pass"
}
```

These are illustrative schemas unless the implementation uses them exactly.

### Bridge abstraction

```text
BridgeTransport
├── OfficeKitAdapter
├── LocalTransport
└── MockTransport
```

Do not assume undocumented Office Kit APIs. Keep the transport abstraction independent of the event mechanism.

---

# 14. Safety Architecture

AI should never directly control unrestricted desktop execution.

```text
AI Decision
     ↓
Schema Validation
     ↓
Safety Policy
     ↓
Allow / Confirm / Reject
     ↓
Deterministic Executor
```

### Action classes

```text
READ_ONLY
SAFE_WRITE
SENSITIVE
DESTRUCTIVE
```

Potential confirmation-required operations:

- delete files
- force Git operations
- destructive shell commands
- credential entry
- system configuration changes
- irreversible actions

The system should stop on:

- low confidence
- repeated failure
- unexpected output
- no meaningful state change
- bridge timeout
- invalid action schema

---

# 15. Verification Architecture

JEVON's strongest differentiator should be the verification loop.

```text
ACTION
  ↓
OBSERVE
  ↓
COLLECT EVIDENCE
  ↓
VERIFY
  ↓
CONTINUE / STOP
```

Potential verification evidence:

- compiler exit status
- test result
- build result
- terminal output
- process state
- expected file change
- expected UI state

The verification layer must remain independent from the decision model so that the model cannot simply declare its own success.

---

# 16. Recommended MVP

The 30-hour build should not attempt to become a general-purpose autonomous software engineer.

### MVP

> **JEVON diagnoses a controlled developer build failure, chooses the next action, executes it through the phone↔laptop workflow, observes the result, and verifies the outcome.**

### Demo sequence

```text
1. Build fails.
2. Developer opens JEVON on iQOO phone.
3. Developer says: "Fix the build."
4. Phone processes local context.
5. Decision engine selects the next bounded action.
6. Safety layer checks the action.
7. Phone requests execution.
8. Laptop performs the action.
9. Result returns to phone.
10. JEVON chooses the next action.
11. Targeted test/build runs.
12. Verification confirms success.
13. Phone shows the final verified state.
```

The complete workflow should remain understandable without explaining the internals for several minutes.

---

# 17. Green Light / Red Light Behavior

The official iQOO guide describes two build conditions: **Green Light** uses both devices, while **Red Light** is phone-only via Office Kit.

JEVON should therefore support both modes conceptually.

### Green Light

```text
Phone
AI + Decision + Control
      ↕
Bridge
      ↕
Laptop
IDE + Terminal + Build + Test
```

### Red Light

```text
Phone
Local AI + Decision + State + UI
      ↓
Continue local work
      ↓
Queue / prepare actions
```

The product should not become unusable simply because the laptop path is temporarily unavailable.

---

# 18. iQOO Developer Tools Track Alignment

The official iQOO Hackathon guide defines Developer Tools as:

> “Build tools that help developers create, test, deploy, or collaborate faster using AI.”

JEVON fits this track because its core job is to improve a concrete developer workflow through AI-assisted perception, decision, execution, and verification.

### Alignment matrix

| Track requirement | JEVON response |
|---|---|
| **Developer tool** | Developer workflow control and automation |
| **Create** | Execute controlled code/project operations |
| **Test** | Select and run targeted tests |
| **Debug** | Diagnose state and choose next actions |
| **Deploy** | Future extension through typed deployment actions |
| **AI** | Local perception and structured decision layer |
| **Phone-first** | iQOO phone as intelligence/control surface |
| **Local/open-source AI** | Primary architectural target |
| **Snapdragon NPU** | Target backend where supported and measured |
| **Office Kit** | Phone/laptop bridge |
| **Verification** | Build/test/evidence-based completion |

---

# 19. Official Judging Alignment

The current official guide lists six judging dimensions totaling 100%:

| Dimension | Weight | JEVON strategy |
|---|---:|---|
| End product quality | 30% | Make one workflow reliable and usable |
| Novelty & impact | 20% | Focus on executable decision intelligence rather than chat-only assistance |
| Creative phone use | 15% | Perform meaningful local AI work on the phone |
| Technical depth | 15% | Local inference, decision contracts, safety, bridge, execution, verification |
| Office Kit usage | 10% | Make phone↔laptop interaction a real architectural component |
| Demo & presentation | 10% | One visible 3–5 minute closed-loop demonstration |

The official guide should be treated as the current source of truth for event rules and scoring.

---

# 20. What Makes JEVON Different

JEVON should not compete with coding assistants by trying to generate more text.

Its architectural distinction is:

```text
CHAT-FIRST AI

Question
 ↓
Answer
 ↓
Human interprets
```

versus:

```text
DECISION-FIRST AI

State
 ↓
Bounded choices
 ↓
Decision
 ↓
Execution
 ↓
Evidence
 ↓
Verification
```

The product proposition is therefore:

> **JEVON turns AI from a conversational helper into a controlled developer workflow component.**

This is a positioning statement, not a claim that JEVON universally outperforms existing coding assistants.

---

# 21. Truth-First Engineering Model

JEVON's design should follow the supplied Truth-First Engine methodology.

The relevant principles are:

```text
UNDERSTAND
    ↓
DIVERSIFY
    ↓
CHALLENGE
    ↓
VERIFY
    ↓
ELIMINATE
    ↓
COMPARE
    ↓
SYNTHESIZE
    ↓
SELECT
    ↓
SELF-CHECK
```

The technical implementation should distinguish:

```text
FACT
DERIVATION
INFERENCE
HYPOTHESIS
ASSUMPTION
ESTIMATE
UNKNOWN
```

The same principle applies to agentic execution:

```text
PLAN
 ↓
EXECUTE
 ↓
OBSERVE
 ↓
VERIFY
 ↓
UPDATE
 ↓
CONTINUE
```

This makes verification a product behavior rather than a documentation slogan.

---

# 22. Performance and Benchmarking

Do not publish performance numbers until they have been measured on actual hardware.

Measure independently:

| Metric | Measurement |
|---|---|
| Perception latency | Input capture → structured state |
| Local inference latency | Model invocation → output |
| Decision latency | State available → selected action |
| Bridge latency | Phone request → laptop receipt |
| Execution latency | Dispatch → observed result |
| Verification latency | Result → verified state |
| End-to-end workflow latency | Start → verified state |
| Memory | Peak working memory |
| CPU/GPU/NPU | Actual runtime backend/telemetry |
| Thermal behavior | Observed under repeated workload |

### Benchmark rule

> **No invented benchmark, no copied benchmark, no unverified hardware claim.**

TypeSafe's computer-use repository publishes its own measurements comparing its Jev-based workflow with a particular frontier-model setup. Those are project-specific measurements and must not be reused as JEVON performance claims.

---

# 23. Offline and Privacy Model

The intended core architecture is local-first wherever practical.

The project should explicitly distinguish:

```text
LOCAL
- local perception
- local model inference
- local state
- local safety
- local verification

OPTIONAL REMOTE
- TypeSafe/JEV provider
- other cloud services
```

Do not describe the application as “fully offline,” “zero cloud,” or “100% private” unless the entire claimed workflow has been tested to support that statement.

Secrets must never enter diagnostic logs.

---

# 24. Failure Modes

JEVON should be designed for failure rather than assuming perfect AI decisions.

| Failure | Required behavior |
|---|---|
| Model unavailable | Fall back or stop safely |
| NPU unavailable | Select another verified backend |
| Low confidence | Request confirmation / stop |
| OCR failure | Re-perceive or report unknown |
| Bridge disconnected | Queue, stop, or return control |
| Action rejected | Surface reason |
| No state change | Detect possible no-op |
| Repeated failure | Stop repeated automation |
| Verification failure | Do not declare success |
| Unexpected state | Re-enter perception/decision |

---

# 25. Repository Architecture Target

A logical target structure is:

```text
jevon/
│
├── core/
│   ├── actions/
│   ├── state/
│   ├── workflow/
│   ├── policies/
│   └── protocol/
│
├── perception/
│   ├── ocr/
│   ├── vision/
│   └── context/
│
├── decision/
│   ├── local/
│   ├── typesafe/
│   └── fallback/
│
├── execution/
│   ├── windows/
│   ├── terminal/
│   ├── ide/
│   └── git/
│
├── verification/
│   ├── build/
│   ├── tests/
│   └── runtime/
│
├── safety/
│
├── bridge/
│   ├── protocol/
│   ├── transport/
│   └── officekit/
│
├── android/
│   ├── ui/
│   ├── local_ai/
│   ├── voice/
│   ├── perception/
│   ├── decision/
│   ├── bridge/
│   └── verification/
│
├── desktop/
│   ├── windows/
│   ├── uiautomation/
│   ├── terminal/
│   ├── ide/
│   └── execution/
│
└── benchmarks/
```

This is an architectural target. Existing repository boundaries should be preserved when they are already cleaner.

---

# 26. Implementation Priorities

## P0 — Required

- Android phone surface
- local AI path
- structured decision provider
- bounded action schema
- safety gate
- phone↔laptop communication
- one real developer workflow
- execution
- verification
- diagnostics/logging

## P1 — High value

- local voice input
- richer OCR/perception
- decision trace
- benchmark dashboard
- offline-mode polish
- improved failure recovery

## P2 — Only if time remains

- second developer workflow
- richer Git actions
- extended IDE support
- additional model providers
- advanced deployment actions

### Scope rule

> **One deeply integrated workflow is more valuable than many partially working agent capabilities.**

---

# 27. Demo Script

### Problem

A controlled project has a real build/test failure.

### Interaction

Developer opens JEVON on the iQOO phone and says:

> **“Fix the build.”**

### On the phone

```text
CURRENT STATE
Build failed

NEXT ACTION
inspect_error

CONFIDENCE
[measured runtime value]

SAFETY
Allowed / Confirmation required
```

### On the laptop

The selected action is executed.

### Loop

```text
Observe
 ↓
Decision
 ↓
Execute
 ↓
Observe
 ↓
Test
 ↓
Verify
```

### Final state

```text
BUILD VERIFIED

Actions executed: [actual]
Verification: PASS
AI backend: [actual]
End-to-end time: [measured]
```

The phone should visibly perform meaningful work throughout the demonstration.

---

# 28. Acceptance Criteria

JEVON should not be called “iQOO-aligned” until the implementation can answer these questions with evidence:

1. What meaningful computation occurs on the phone?
2. What local model or inference runtime performs it?
3. Which decision happens locally?
4. What is the role of the JEV/JEV-style provider?
5. What does Office Kit / the bridge contribute?
6. What does the laptop execute?
7. What evidence verifies that an action succeeded?
8. What happens when the device is offline?
9. What happens when confidence is low?
10. What happens when the bridge fails?
11. Can the phone still operate meaningfully without the laptop?
12. Can the complete core workflow be demonstrated on the iQOO device?
13. Are the performance claims measured?
14. Is the system visibly different from a normal chatbot?
15. Is the workflow clearly a Developer Tool?

---

# 29. What We Must Not Claim Without Evidence

Do not claim any of the following unless verified in the current implementation and test environment:

- “fully on-device”
- “NPU accelerated”
- “zero cloud”
- “zero latency”
- “sub-second”
- “zero cost”
- “100% private”
- “production-ready”
- “fully autonomous”
- “secure by design”
- “more accurate than frontier models”
- “novel / never done before”
- “guaranteed reliable”

Use explicit status labels instead:

```text
IMPLEMENTED
EXPERIMENTAL
PLANNED
UNVERIFIED
UNKNOWN
```

---

# 30. Conclusion

JEVON is not an attempt to make another conversational coding assistant. It is a developer workflow architecture built around a different abstraction:

> **AI should not only answer what the developer should do; it should help select the next bounded action, execute it safely, observe the result, and verify whether the workflow progressed.**

The iQOO phone becomes the local intelligence and control surface. The laptop remains the practical developer execution environment. The bridge connects the two. Deterministic tooling performs actions, while verification provides evidence that the system has actually succeeded.

The strongest hackathon implementation is therefore:

```text
LOCAL PERCEPTION
      ↓
STRUCTURED DECISION
      ↓
SAFETY GATE
      ↓
DETERMINISTIC EXECUTION
      ↓
OBSERVATION
      ↓
VERIFICATION
      ↓
NEXT DECISION
```

### Final one-line definition

> **JEVON is a phone-first AI developer control layer that converts development state into safe, structured actions and closes the loop with real execution and verification.**

---

# References and Source Basis

### Official event

1. **iQOO Hackathon 2026 — Guide & Rules**  
   https://iqoo.reskilll.com/guide  
   Source for track definitions, phone-first rules, local/open-source model guidance, Snapdragon NPU targeting, Office Kit, judging weights, and build rules. Accessed September 22, 2026.

### TypeSafe / JEV

2. **TypeSafe AI — System One Models / Jev**  
   https://typesafe.ai/  
   Source for TypeSafe's public positioning of structured decision intelligence and Jev.

3. **awlevin/typesafe-computer-use**  
   https://github.com/awlevin/typesafe-computer-use  
   Source for the public computer-use implementation pattern: deterministic screen perception, bounded action selection, TypeSafe decisioning, deterministic execution, and project-specific benchmark reporting.

### Methodology supplied for this project

4. **ULTIMATE N-PERSPECTIVE TRUTH-FIRST ENGINE**  
   User-supplied project methodology. Used as the design/validation framework for fact-vs-unknown separation, adversarial analysis, evidence gating, feasibility levels, and verification loops.

---

## Document Status

**Purpose:** Architecture + problem framing + hackathon alignment  
**Status:** Design specification  
**Target:** iQOO Hackathon 2026 — Developer Tools  
**Principle:** Explore widely. Verify aggressively. Build narrowly. Demonstrate honestly.

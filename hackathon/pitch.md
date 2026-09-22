# Argus: 3-Minute Hackathon Pitch & Stage Script

**Track:** Developer Tools  
**Device:** iQOO 15 (Snapdragon 8 Elite Gen 5, Hexagon NPU, OriginOS 6)  
**Time Limit:** 3 minutes presentation + 2 minutes Q&A  

---

## The Pitch Script

### [0:00 - 0:30] The Hook & The Problem
> *"Good afternoon, judges. Every mobile developer in the world shares the exact same headache: UI and regression testing on physical devices is painful. Writing Appium or Espresso scripts takes hours, locators break whenever the UI shifts 2 pixels, and running end-to-end tests requires cloud device farms or slow emulators.*  
>
> *Today, developers carry a supercomputer in their pocket — the iQOO 15 with the Snapdragon 8 Elite Gen 5 and a 45+ TOPS Hexagon NPU. Why are we sending UI automation tasks to remote cloud servers when the phone itself can perceive, think, and test itself in real time?*  
>
> *Meet **Argus** — the world's first voice-driven, autonomous mobile testing agent that runs 100% on-device on the iQOO 15."*

---

### [0:30 - 1:45] The Live Demo (Watch the Phone Do the Work)
*(Action: Hold the phone towards the audience, while Office Kit mirrors the 1080p 60fps display on the projector)*

> *"I won't write a single line of test code. I'm just going to speak to the phone."*

*(Speak into the microphone)*:  
> **"Argus, test the arithmetic calculator flow: calculate 25 plus 75."**

*(What happens live on stage)*:
1. **Microphone lights up**: Snapdragon NPU transcribes the voice query using on-device Whisper in under 1 second.
2. **Phone speaks aloud**: *"Understood: calculate 25 plus 75. Starting test."*
3. **App launches autonomously**: Argus triggers the target app via ADB self-connection.
4. **On-Device Perception**: Argus extracts the UI tree and hardware OCR directly in RAM.
5. **On-Device SLM Reasoning**: The quantized Qwen 2.5 model running on the Hexagon NPU decides the next action (Tap '2', tap '5', tap '+', tap '7', tap '5', tap '=').
6. **Execution**: Automated touch gestures fire across the screen.
7. **Verification**: Argus reads the result display ('100'), verifies correctness, and stops.
8. **Phone speaks**: *"Test passed. 6 steps completed in 8.4 seconds. Report generated."*

*(Action: Click the Office Kit window on the laptop)*:
> *"Instantly, via iQOO Office Kit, the complete HTML test report, annotated step-by-step screenshots, and timing telemetry are synced to the developer's laptop."*

---

### [1:45 - 2:30] Technical Depth & Architecture
> *"How does this work without any cloud APIs?*
> 1. **Perception**: Self-loopback ADB pulls UIAutomator hierarchy XML and hardware display frames with zero network latency.
> 2. **Reasoning on Hexagon NPU**: We replaced cloud LLMs with an on-device quantized Qwen 2.5 SLM compiled for Snapdragon NPU execution via ONNX Runtime & QNN. Every decision takes under 600 milliseconds.
> 3. **Speech Pipeline**: Whisper STT and Android Speech Synthesis run entirely offline.
> 4. **Zero-Cloud Privacy & Cost**: No OpenAI bills, no API tokens, no sensitive user data leaving the device boundary."*

---

### [2:30 - 3:00] Impact & Future Roadmap
> *"With Argus, any QA engineer or mobile developer can run comprehensive regression suites by speaking natural language scenarios during their commute, at their desk, or integrated into local mobile CI/CD pipelines via iQOO Office Kit.*  
>
> *We're bringing true autonomous agentic compute to the edge. Thank you!"*

---

## Anticipated Jury Q&A & Winning Answers

### Q1: "How is this different from existing tools like Appium or Maestro?"
> **Answer:** *"Appium and Maestro require developers to write and maintain explicit locator scripts (XPath, resource-ids) which break when UI designs change. Argus is an autonomous agent: it visually perceives the screen and reasons about how to accomplish the user's intent dynamically. If a button moves from top-right to bottom-left, Argus still finds and clicks it without script modification."*

### Q2: "Are you really running the model on the phone, or is it calling a backend?"
> **Answer:** *"It is 100% on-device. You can disconnect Wi-Fi and pull the SIM card right now, and the entire loop — Whisper voice recognition, screen perception, Qwen 2.5 decision inference, and speech synthesis — will continue running seamlessly on the Snapdragon 8 Elite Hexagon NPU. HackTracker telemetry verifies the continuous NPU hardware acceleration."*

### Q3: "How does Office Kit fit into this?"
> **Answer:** *"Office Kit serves as the professional developer bridge. While the phone executes tests autonomously, the developer monitors live execution on their PC screen, reviews detailed HTML reports synced over Office Kit file transfer, and copies test summaries to their clipboard without plugging and unplugging devices."*

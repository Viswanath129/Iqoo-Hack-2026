# iQOO Office Kit Setup & Telemetry Guide

## Overview

**iQOO Office Kit** is the official desktop companion suite (`pc.vivoglobal.com`) that bridges the iQOO 15 phone and your laptop.

In the hackathon, Office Kit drives **10% of your total project score** via HackTracker telemetry:
- Screen mirroring uptime
- Remote control events
- Clipboard sync transactions
- Drag-and-drop file transfers

---

## 1. Pre-Hackathon / Check-in Pairing

1. Download & install **iQOO Office Kit** on your laptop from [pc.vivoglobal.com](https://pc.vivoglobal.com).
2. Connect your iQOO 15 phone via USB-C cable (or low-latency 5GHz Wi-Fi).
3. On the phone, accept the **"Trust this computer"** prompt and grant Office Kit permissions.
4. Launch Office Kit on laptop → click **"Phone Screen Mirroring"**.

---

## 2. Setting up the Developer Testing View

During the live demo, set up your workstation like this:

- **Laptop Display:**
  - **Left 60% of Screen:** Office Kit Window showing the live phone mirror in 1080p 60fps.
  - **Right 40% of Screen:** Terminal/Browser showing real-time test logs and HTML test reports.
- **iQOO 15 Phone:**
  - Kept visible on the desk or held in hand for voice commands into the microphone.

---

## 3. Maximizing HackTracker Telemetry (The 10% Office Kit Score)

HackTracker logs specific interaction channels:

| Channel | How Argus Triggers It | Frequency |
|---|---|---|
| **Screen Mirroring** | Keep the Office Kit mirror active for the entire session | 100% of demo time |
| **Clipboard Sync** | When Argus completes a test, copy the summary text to clipboard | After every test run |
| **File Transfer** | Drag the generated HTML report and `annotated.png` from phone to PC | End of every demo |
| **Input Events** | Use laptop keyboard/mouse to click phone via Office Kit during Red Light | Continuously |

---

## 4. Red Light Compliance Strategy

During the 55% Red Light (Phone-Only) windows:
1. Do NOT code directly in your laptop IDE on local files.
2. Interface with the phone **exclusively through Office Kit**:
   - Open Termux on the phone's mirrored screen.
   - Use your laptop keyboard to write scripts inside the mirrored Termux window.
   - Run tests directly on the phone via Termux terminal.
3. HackTracker will register this as compliant phone-first development via the official Office Kit bridge!

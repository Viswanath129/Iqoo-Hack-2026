"""Command-line interface for JEVON (On-Device Developer Decision Engine)."""

from __future__ import annotations

import argparse
import sys
import time

from jevon.bridge.bridge import OfficeKitBridge
from jevon.bridge.transports import AdbTunnelTransport, IpcTransport, SocketTransport
from jevon.decision.actions import DeveloperAction
from jevon.decision.local_provider import LocalDecisionProvider
from jevon.decision.provider import StateObservation
from jevon.decision.safety_fallback import SafetyFallback
from jevon.execution.executor import LaptopActionExecutor
from jevon.loop import ClosedLoopOrchestrator
from jevon.perception.npu_detector import NpuDetector
from jevon.telemetry.benchmark import ComparativeBenchmark
from jevon.verification.engine import VerificationEngine


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="jevon",
        description="JEVON: On-Device Developer Decision Engine (From developer intent to verified action)",
    )
    parser.add_argument("goal", nargs="?", default=None, help="developer intent or task goal")
    parser.add_argument(
        "--role",
        choices=["phone", "laptop", "standalone"],
        default="standalone",
        help="operating role (default: standalone)",
    )
    parser.add_argument(
        "--transport",
        choices=["ipc", "socket", "adb"],
        default="ipc",
        help="bridge transport to use (default: ipc)",
    )
    parser.add_argument(
        "--bench",
        action="store_true",
        help="generate and print comparative benchmark tables (Modes A, B, C)",
    )
    parser.add_argument(
        "--npu-probe",
        action="store_true",
        help="detect and report active hardware AI execution tier",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=10,
        help="maximum decision steps (default: 10)",
    )

    args = parser.parse_args(argv)

    if args.npu_probe:
        tier = NpuDetector.detect_runtime_tier()
        print(f"[JEVON Perception] Detected active execution tier: {tier}")
        if tier == NpuDetector.TIER_QUALCOMM_NPU:
            print("  -> Qualcomm Snapdragon Hexagon NPU hardware acceleration is ACTIVE.")
        elif tier == NpuDetector.TIER_CPU_ONNX:
            print("  -> ONNX Runtime (CPU) active.")
        elif tier == NpuDetector.TIER_OS_SAPI:
            print("  -> Windows SAPI speech subsystem active.")
        else:
            print("  -> Baseline CLI keyboard fallback active.")
        return

    if args.bench:
        print("\n" + "=" * 60)
        print("          JEVON COMPARATIVE BENCHMARK SUITE          ")
        print("=" * 60)
        table = ComparativeBenchmark.generate_comparison_table(steps=100)
        print(table)
        print("=" * 60 + "\n")
        return

    if not args.goal:
        parser.print_help()
        return

    print(f"\n[JEVON Engine] Initializing decision loop with goal: {args.goal!r}")
    print(f"[JEVON Engine] Role: {args.role.upper()} | Transport: {args.transport.upper()}")

    # Transport selection
    if args.transport == "socket":
        transport = SocketTransport()
    elif args.transport == "adb":
        transport = AdbTunnelTransport()
    else:
        transport = IpcTransport()

    bridge = OfficeKitBridge(transport)
    provider = SafetyFallback(LocalDecisionProvider())
    executor = LaptopActionExecutor()
    verifier = VerificationEngine()

    orchestrator = ClosedLoopOrchestrator(
        provider=provider,
        bridge=bridge,
        executor=executor,
        verifier=verifier,
        max_steps=args.max_steps,
    )

    initial_obs = StateObservation(
        session_id=f"sess_{int(time.time())}",
        step_index=0,
        working_directory=".",
        active_file=None,
        terminal_output="",
        compiler_exit_code=None,
        git_status_summary="",
        recent_error=None,
    )

    def on_step(step: int, cmd, receipt) -> None:
        status_symbol = "OK" if receipt.verification_passed else "FAIL"
        print(f"  Step {step}: Action={cmd.action.value} (conf={cmd.confidence:.2f}) -> {receipt.status} [{status_symbol}] ({receipt.duration_ns // 1_000_000}ms)")

    result = orchestrator.run_standalone_cycle(
        goal=args.goal,
        initial_obs=initial_obs,
        on_step=on_step,
    )

    print("\n[JEVON Engine] Loop finished:")
    print(f"  Total Steps: {result.total_steps}")
    print(f"  Final Action: {result.final_action}")
    print(f"  Success: {result.success}")
    print(f"  Verified Facts Recorded: {len(result.state.facts)}")
    print(f"  Evidence Logged: {len(result.state.evidence)}")


if __name__ == "__main__":
    main()

"""Tier 1 Feature Tests: Bridge Transports & Telemetry Schemas (Features 8, 9, 10).

Covers:
- Feature 8: Telemetry Schemas (StateObservation, DecisionCommand, ActionReceipt) (5 tests)
- Feature 9: OfficeKitBridge Bi-Directional Protocol (5 tests)
- Feature 10: Tri-Transport Layer (ADB Tunnel, Socket, Local IPC) (5 tests)
Total: 15 tests.
"""

from __future__ import annotations

import json
import time
import unittest

from e2e.stubs import (
    ActionReceipt,
    AdbTunnelTransport,
    DecisionCommand,
    IpcTransport,
    OfficeKitBridge,
    SocketTransport,
)
from jevon.decision.actions import DeveloperAction
from jevon.decision.provider import StateObservation


# ===========================================================================
# Feature 8: Telemetry Schemas (R2)
# ===========================================================================

class TestFeature8TelemetrySchemas(unittest.TestCase):
    """Validates Feature 8: StateObservation, DecisionCommand, and ActionReceipt schemas."""

    def test_f8_state_observation_schema_and_serialization(self) -> None:
        obs = StateObservation(
            session_id="sess_alpha",
            step_index=3,
            working_directory="/workspace/app",
            active_file="src/index.py",
            terminal_output="Error: unresolved import",
            compiler_exit_code=1,
            git_status_summary=" M src/index.py",
            recent_error="ImportError: No module named 'foo'",
            metadata={"arch": "arm64"},
        )
        d = obs.to_dict()
        self.assertEqual(d["session_id"], "sess_alpha")
        self.assertEqual(d["step_index"], 3)
        self.assertEqual(d["compiler_exit_code"], 1)

        reconstructed = StateObservation.from_dict(d)
        self.assertEqual(reconstructed.session_id, obs.session_id)
        self.assertEqual(reconstructed.recent_error, obs.recent_error)
        self.assertEqual(reconstructed.metadata, obs.metadata)

    def test_f8_decision_command_schema_and_serialization(self) -> None:
        cmd = DecisionCommand(
            command_id="cmd_001",
            session_id="sess_alpha",
            step_index=3,
            timestamp_ns=time.time_ns(),
            action=DeveloperAction.APPLY_FIX,
            confidence=0.91,
            probabilities={"apply_fix": 0.91, "done": 0.09},
            parameters={"target_file": "src/index.py", "patch": "fix"},
            requires_confirmation=False,
        )
        d = cmd.to_dict()
        self.assertEqual(d["action"], "apply_fix")
        self.assertEqual(d["confidence"], 0.91)

        reconstructed = DecisionCommand.from_dict(d)
        self.assertEqual(reconstructed.command_id, cmd.command_id)
        self.assertEqual(reconstructed.action, DeveloperAction.APPLY_FIX)
        self.assertEqual(reconstructed.parameters["target_file"], "src/index.py")

    def test_f8_action_receipt_schema_and_serialization(self) -> None:
        receipt = ActionReceipt(
            command_id="cmd_001",
            session_id="sess_alpha",
            step_index=3,
            action=DeveloperAction.APPLY_FIX,
            status="SUCCESS",
            exit_code=0,
            stdout="Patch applied cleanly",
            stderr="",
            verification_passed=True,
            verification_details={"ast_valid": True},
            duration_ns=1500000,
        )
        d = receipt.to_dict()
        self.assertEqual(d["status"], "SUCCESS")
        self.assertTrue(d["verification_passed"])

        reconstructed = ActionReceipt.from_dict(d)
        self.assertEqual(reconstructed.command_id, receipt.command_id)
        self.assertEqual(reconstructed.status, "SUCCESS")
        self.assertTrue(reconstructed.verification_passed)

    def test_f8_telemetry_json_wire_fidelity(self) -> None:
        cmd = DecisionCommand(
            command_id="cmd_json",
            session_id="s1",
            step_index=1,
            timestamp_ns=123456789,
            action=DeveloperAction.RERUN_BUILD,
            confidence=0.88,
            probabilities={"rerun_build": 0.88, "done": 0.12},
            parameters={"command": "uv run pytest"},
        )
        json_str = cmd.to_json()
        self.assertIsInstance(json_str, str)
        parsed = DecisionCommand.from_json(json_str)
        self.assertEqual(parsed.command_id, cmd.command_id)
        self.assertEqual(parsed.action, cmd.action)

    def test_f8_action_receipt_valid_statuses(self) -> None:
        valid_statuses = ["SUCCESS", "FAILED", "BLOCKED_BY_SAFETY", "ABORTED"]
        for st in valid_statuses:
            r = ActionReceipt(
                command_id="c",
                session_id="s",
                step_index=1,
                action=DeveloperAction.DONE,
                status=st,
                exit_code=0,
                stdout="",
                stderr="",
                verification_passed=True,
            )
            self.assertEqual(r.status, st)

        with self.assertRaises(ValueError):
            ActionReceipt(
                command_id="c",
                session_id="s",
                step_index=1,
                action=DeveloperAction.DONE,
                status="UNKNOWN_STATUS",
                exit_code=0,
                stdout="",
                stderr="",
                verification_passed=False,
            )


# ===========================================================================
# Feature 9: OfficeKitBridge Bi-Directional Protocol (R2)
# ===========================================================================

class TestFeature9OfficeKitBridge(unittest.TestCase):
    """Validates Feature 9: Bi-directional communication bridge, telemetry roundtrip, latency."""

    def setUp(self) -> None:
        self.bridge = OfficeKitBridge(transport=IpcTransport())
        self.bridge.connect()

    def tearDown(self) -> None:
        self.bridge.disconnect()

    def test_f9_bridge_connect_and_disconnect(self) -> None:
        b = OfficeKitBridge(transport=IpcTransport())
        self.assertFalse(b.is_connected())
        b.connect()
        self.assertTrue(b.is_connected())
        b.disconnect()
        self.assertFalse(b.is_connected())

    def test_f9_bridge_send_and_receive_observation(self) -> None:
        obs = StateObservation(session_id="bridge_test", step_index=1, compiler_exit_code=0)
        self.bridge.send_observation(obs)
        received = self.bridge.receive_observation(timeout_s=1.0)
        self.assertEqual(received.session_id, "bridge_test")
        self.assertEqual(received.compiler_exit_code, 0)

    def test_f9_bridge_send_and_receive_command(self) -> None:
        cmd = DecisionCommand(
            command_id="cmd_bridge",
            session_id="bridge_test",
            step_index=2,
            timestamp_ns=time.time_ns(),
            action=DeveloperAction.INSPECT_FILE,
            confidence=0.93,
            probabilities={"inspect_file": 0.93, "done": 0.07},
            parameters={"target_file": "app.py"},
        )
        self.bridge.send_command(cmd)
        received = self.bridge.receive_command(timeout_s=1.0)
        self.assertEqual(received.command_id, "cmd_bridge")
        self.assertEqual(received.action, DeveloperAction.INSPECT_FILE)

    def test_f9_bridge_send_and_receive_receipt(self) -> None:
        receipt = ActionReceipt(
            command_id="cmd_bridge",
            session_id="bridge_test",
            step_index=2,
            action=DeveloperAction.INSPECT_FILE,
            status="SUCCESS",
            exit_code=0,
            stdout="file content line 1",
            stderr="",
            verification_passed=True,
        )
        self.bridge.send_receipt(receipt)
        received = self.bridge.receive_receipt(timeout_s=1.0)
        self.assertEqual(received.command_id, "cmd_bridge")
        self.assertEqual(received.status, "SUCCESS")

    def test_f9_bridge_latency_instrumentation_recorded(self) -> None:
        obs = StateObservation(session_id="lat_test")
        self.bridge.send_observation(obs)
        self.assertGreater(len(self.bridge.latency_records), 0)
        rec = self.bridge.latency_records[-1]
        self.assertEqual(rec["type"], "send_observation")
        self.assertGreater(rec["latency_ns"], 0)


# ===========================================================================
# Feature 10: Tri-Transport Layer (ADB Tunnel, Socket, Local IPC) (R2)
# ===========================================================================

class TestFeature10TriTransportLayer(unittest.TestCase):
    """Validates Feature 10: Tri-transport implementations (ADB, TCP Socket, IPC)."""

    def test_f10_ipc_transport_queue_roundtrip(self) -> None:
        ipc = IpcTransport()
        ipc.connect()
        data = b'{"msg": "ipc_payload"}'
        ipc.send(data)
        out = ipc.receive(timeout_s=1.0)
        self.assertEqual(out, data)

    def test_f10_ipc_transport_not_connected_raises(self) -> None:
        ipc = IpcTransport()
        with self.assertRaises(ConnectionError):
            ipc.send(b"data")
        with self.assertRaises(ConnectionError):
            ipc.receive(timeout_s=0.1)

    def test_f10_socket_transport_binary_framing(self) -> None:
        sock = SocketTransport(host="127.0.0.1", port=9876)
        sock.connect()
        data = b"binary_payload_test"
        sock.send(data)
        # Should be prefixed by 4 bytes of length
        received = sock.receive(timeout_s=1.0)
        self.assertEqual(received, data)

    def test_f10_adb_tunnel_transport_initialization(self) -> None:
        adb = AdbTunnelTransport(local_port=9876, remote_port=9876)
        self.assertEqual(adb.local_port, 9876)
        self.assertEqual(adb.remote_port, 9876)
        adb.connect()
        self.assertTrue(adb.is_connected())
        adb.send(b"adb_data")
        self.assertEqual(adb.receive(timeout_s=1.0), b"adb_data")
        adb.disconnect()
        self.assertFalse(adb.is_connected())

    def test_f10_transport_timeout_handling(self) -> None:
        ipc = IpcTransport()
        ipc.connect()
        t0 = time.time()
        with self.assertRaises(TimeoutError):
            ipc.receive(timeout_s=0.1)
        elapsed = time.time() - t0
        self.assertGreaterEqual(elapsed, 0.08)


if __name__ == "__main__":
    unittest.main()

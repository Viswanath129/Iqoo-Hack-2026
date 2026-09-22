"""Tier 2 Boundary Tests: Network Timeouts & Bridge Boundary Cases (Features 8, 9, 10).

Covers:
- Feature 8: Telemetry Schemas (5 boundary tests)
- Feature 9: OfficeKitBridge (5 boundary tests)
- Feature 10: Tri-Transport Layer (5 boundary tests)
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
# Feature 8 Boundary Cases: Telemetry Schemas
# ===========================================================================

class TestFeature8TelemetryBoundaries(unittest.TestCase):
    """Boundary conditions for telemetry schemas."""

    def test_b8_state_observation_huge_metadata_payload(self) -> None:
        large_meta = {f"k_{i}": f"v_{i}" for i in range(1000)}
        obs = StateObservation(metadata=large_meta)
        d = obs.to_dict()
        reconstructed = StateObservation.from_dict(d)
        self.assertEqual(len(reconstructed.metadata), 1000)

    def test_b8_decision_command_zero_confidence(self) -> None:
        cmd = DecisionCommand(
            command_id="cmd_zero",
            session_id="s",
            step_index=0,
            timestamp_ns=time.time_ns(),
            action=DeveloperAction.DONE,
            confidence=0.0,
            probabilities={"done": 0.0},
        )
        json_str = cmd.to_json()
        reconstructed = DecisionCommand.from_json(json_str)
        self.assertEqual(reconstructed.confidence, 0.0)

    def test_b8_action_receipt_negative_exit_code(self) -> None:
        receipt = ActionReceipt(
            command_id="c_sigkill",
            session_id="s",
            step_index=1,
            action=DeveloperAction.RERUN_BUILD,
            status="FAILED",
            exit_code=-9,  # Process killed by SIGKILL
            stdout="",
            stderr="Killed",
            verification_passed=False,
        )
        self.assertEqual(receipt.exit_code, -9)
        d = receipt.to_dict()
        self.assertEqual(d["exit_code"], -9)

    def test_b8_telemetry_special_characters_in_ids(self) -> None:
        strange_id = "session:!@#$%^&*()_+/{}|[]\\:\"'<>?,."
        obs = StateObservation(session_id=strange_id)
        d = obs.to_dict()
        self.assertEqual(d["session_id"], strange_id)

    def test_b8_action_receipt_empty_strings(self) -> None:
        receipt = ActionReceipt(
            command_id="",
            session_id="",
            step_index=0,
            action=DeveloperAction.DONE,
            status="SUCCESS",
            exit_code=0,
            stdout="",
            stderr="",
            verification_passed=True,
        )
        self.assertEqual(receipt.stdout, "")
        self.assertEqual(receipt.stderr, "")


# ===========================================================================
# Feature 9 Boundary Cases: OfficeKitBridge
# ===========================================================================

class TestFeature9OfficeKitBridgeBoundaries(unittest.TestCase):
    """Boundary conditions for OfficeKitBridge."""

    def test_b9_bridge_send_when_disconnected_raises(self) -> None:
        bridge = OfficeKitBridge(transport=IpcTransport())
        obs = StateObservation()
        with self.assertRaises(ConnectionError):
            bridge.send_observation(obs)

    def test_b9_bridge_receive_timeout_zero_s(self) -> None:
        bridge = OfficeKitBridge(transport=IpcTransport())
        bridge.connect()
        t0 = time.time()
        with self.assertRaises(TimeoutError):
            bridge.receive_observation(timeout_s=0.01)
        self.assertLess(time.time() - t0, 0.5)
        bridge.disconnect()

    def test_b9_bridge_multiple_consecutive_reconnects(self) -> None:
        bridge = OfficeKitBridge(transport=IpcTransport())
        for _ in range(10):
            bridge.connect()
            self.assertTrue(bridge.is_connected())
            bridge.disconnect()
            self.assertFalse(bridge.is_connected())

    def test_b9_bridge_corrupted_json_payload(self) -> None:
        ipc = IpcTransport()
        ipc.connect()
        bridge = OfficeKitBridge(transport=ipc)
        bridge.connect()

        # Send raw non-JSON bytes
        ipc.send(b"{corrupted_invalid_json")
        with self.assertRaises(json.JSONDecodeError):
            bridge.receive_observation(timeout_s=1.0)
        bridge.disconnect()

    def test_b9_bridge_high_frequency_burst(self) -> None:
        bridge = OfficeKitBridge(transport=IpcTransport())
        bridge.connect()
        count = 50
        for i in range(count):
            obs = StateObservation(session_id=f"burst_{i}", step_index=i)
            bridge.send_observation(obs)

        for i in range(count):
            rec = bridge.receive_observation(timeout_s=1.0)
            self.assertEqual(rec.step_index, i)
        bridge.disconnect()


# ===========================================================================
# Feature 10 Boundary Cases: Tri-Transport Layer
# ===========================================================================

class TestFeature10TriTransportBoundaries(unittest.TestCase):
    """Boundary conditions for transport protocols."""

    def test_b10_socket_transport_zero_length_frame(self) -> None:
        sock = SocketTransport()
        sock.connect()
        sock.send(b"")
        received = sock.receive(timeout_s=1.0)
        self.assertEqual(received, b"")

    def test_b10_socket_transport_incomplete_frame_header(self) -> None:
        sock = SocketTransport()
        sock.connect()
        # Manually inject only 2 bytes into buffer (needs 4)
        sock._buffer.extend(b"\x00\x01")
        with self.assertRaises(TimeoutError) as ctx:
            sock.receive(timeout_s=0.1)
        self.assertIn("No framed data", str(ctx.exception))

    def test_b10_socket_transport_partial_payload(self) -> None:
        sock = SocketTransport()
        sock.connect()
        # 4 bytes claiming 10 bytes payload, but only 3 bytes present
        length_bytes = (10).to_bytes(4, byteorder="big")
        sock._buffer.extend(length_bytes + b"abc")
        with self.assertRaises(TimeoutError) as ctx:
            sock.receive(timeout_s=0.1)
        self.assertIn("Incomplete socket frame", str(ctx.exception))

    def test_b10_adb_transport_disconnect_mid_transfer(self) -> None:
        adb = AdbTunnelTransport()
        adb.connect()
        adb.disconnect()
        with self.assertRaises(ConnectionError):
            adb.send(b"data_after_disconnect")

    def test_b10_ipc_transport_queue_full_or_empty(self) -> None:
        ipc = IpcTransport()
        ipc.connect()
        with self.assertRaises(TimeoutError):
            ipc.receive(timeout_s=0.01)


if __name__ == "__main__":
    unittest.main()

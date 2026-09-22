"""Comprehensive unit and integration tests for JEVON Office Kit Bridge Layer.

Covers:
- DecisionCommand: creation, bounded actions, confidence limits, serialization round-trips.
- ActionReceipt: status invariants, string coercion, serialization round-trips, validity checks.
- IpcTransport: connection lifecycle, FIFO ordering, timeout handling, and peer_view.
- SocketTransport: 4-byte framing, create_pair cross-wiring, buffer resets, timeouts.
- AdbTunnelTransport: port configuration, connection lifecycle, and inner delegation.
- OfficeKitBridge: command/receipt/observation dispatch, cross-transport exchange, latency metrics.
"""

from __future__ import annotations

import time
from dataclasses import FrozenInstanceError

import pytest

from jevon.bridge.bridge import OfficeKitBridge
from jevon.bridge.protocol import ActionReceipt, DecisionCommand
from jevon.bridge.transports import (
    AdbTunnelTransport,
    IpcTransport,
    SocketTransport,
)
from jevon.decision.actions import DeveloperAction
from jevon.decision.provider import StateObservation


@pytest.fixture
def sample_command() -> DecisionCommand:
    """Canonical valid DecisionCommand fixture."""
    return DecisionCommand(
        command_id="cmd-1001", session_id="sess-dev-01", step_index=3,
        timestamp_ns=1_700_000_000_000, action=DeveloperAction.APPLY_FIX,
        confidence=0.88,
        probabilities={"apply_fix": 0.88, "inspect_error": 0.08, "run_targeted_test": 0.04},
        parameters={"file_path": "src/core.py", "patch": "@@ -1 +1 @@"},
        requires_confirmation=False,
    )


@pytest.fixture
def sample_receipt() -> ActionReceipt:
    """Canonical valid ActionReceipt fixture."""
    return ActionReceipt(
        command_id="cmd-1001", session_id="sess-dev-01", step_index=3,
        action=DeveloperAction.APPLY_FIX, status="SUCCESS", exit_code=0,
        stdout="Patch applied cleanly", stderr="", verification_passed=True,
        verification_details={"tests": "1 passed"}, duration_ns=15_500_000,
        timestamp_ns=1_700_000_015_500,
    )


@pytest.fixture
def sample_observation() -> StateObservation:
    """Canonical valid StateObservation fixture."""
    return StateObservation(
        session_id="sess-dev-01", step_index=2, timestamp_ns=1_700_000_000_000,
        working_directory="/workspace/project", active_file="src/core.py",
        terminal_output="AssertionError: failed", compiler_exit_code=1,
        git_status_summary="M src/core.py", recent_error="AssertionError: failed",
    )


# --- 1. DecisionCommand Tests (9 tests) ---

def test_decision_command_creation_happy_path(sample_command: DecisionCommand) -> None:
    """Verify happy-path initialization of DecisionCommand attributes."""
    assert sample_command.command_id == "cmd-1001" and sample_command.session_id == "sess-dev-01"
    assert sample_command.step_index == 3 and sample_command.action == DeveloperAction.APPLY_FIX
    assert sample_command.confidence == 0.88 and sample_command.requires_confirmation is False
    assert sample_command.parameters["file_path"] == "src/core.py"


def test_decision_command_string_action_coercion() -> None:
    """Strings matching action enum values should be coerced into DeveloperAction."""
    cmd = DecisionCommand("cmd-1", "s", 0, 0, "inspect_error", 0.7, {})  # type: ignore[arg-type]
    assert cmd.action is DeveloperAction.INSPECT_ERROR and isinstance(cmd.action, DeveloperAction)


def test_decision_command_all_bounded_actions() -> None:
    """DecisionCommand should accept every action defined in DeveloperAction."""
    for action in DeveloperAction.all_actions():
        cmd = DecisionCommand(f"cmd-{action.value}", "s", 1, 100, action, 0.5, {})
        assert cmd.action == action


def test_decision_command_invalid_action_raises() -> None:
    """Unrecognized action names should raise ValueError."""
    with pytest.raises(ValueError):
        DecisionCommand("cmd-err", "s", 0, 100, "non_existent", 0.5, {})  # type: ignore[arg-type]


def test_decision_command_confidence_boundaries_and_rejections() -> None:
    """Validate 0.0/1.0 bounds and rejection of confidence outside [0.0, 1.0]."""
    assert DecisionCommand("c1", "s", 0, 0, DeveloperAction.DONE, 0.0, {}).confidence == 0.0
    assert DecisionCommand("c2", "s", 0, 0, DeveloperAction.DONE, 1.0, {}).confidence == 1.0
    with pytest.raises(ValueError, match=r"Confidence -0\.01 must be in \[0\.0, 1\.0\]"):
        DecisionCommand("c3", "s", 0, 0, DeveloperAction.DONE, -0.01, {})
    with pytest.raises(ValueError, match=r"Confidence 1\.01 must be in \[0\.0, 1\.0\]"):
        DecisionCommand("c4", "s", 0, 0, DeveloperAction.DONE, 1.01, {})


def test_decision_command_to_dict_and_from_dict_roundtrip(sample_command: DecisionCommand) -> None:
    """Serializing to dict and rebuilding via from_dict yields an equal instance."""
    data = sample_command.to_dict()
    assert data["action"] == "apply_fix" and data["confidence"] == 0.88
    assert DecisionCommand.from_dict(data) == sample_command


def test_decision_command_from_dict_defaults() -> None:
    """from_dict handles omitted optional fields with sane defaults."""
    cmd = DecisionCommand.from_dict({"command_id": "cmd-def", "action": "rerun_build"})
    assert cmd.command_id == "cmd-def" and cmd.action == DeveloperAction.RERUN_BUILD
    assert cmd.session_id == "" and cmd.step_index == 0 and cmd.confidence == 0.0
    assert cmd.probabilities == {} and cmd.requires_confirmation is False


def test_decision_command_json_roundtrip(sample_command: DecisionCommand) -> None:
    """to_json and from_json serialize and deserialize accurately."""
    payload = sample_command.to_json()
    assert isinstance(payload, str) and DecisionCommand.from_json(payload) == sample_command


def test_decision_command_is_valid_and_immutability(sample_command: DecisionCommand) -> None:
    """is_valid checks command_id presence, and dataclass prevents attribute mutation."""
    assert sample_command.is_valid() is True
    assert DecisionCommand("", "s", 0, 0, DeveloperAction.DONE, 0.5, {}).is_valid() is False
    with pytest.raises(FrozenInstanceError):
        sample_command.confidence = 0.99  # type: ignore[misc]


# --- 2. ActionReceipt Tests (7 tests) ---

def test_action_receipt_creation_happy_path(sample_receipt: ActionReceipt) -> None:
    """Verify happy-path initialization of ActionReceipt attributes."""
    assert sample_receipt.command_id == "cmd-1001" and sample_receipt.session_id == "sess-dev-01"
    assert sample_receipt.action == DeveloperAction.APPLY_FIX and sample_receipt.status == "SUCCESS"
    assert sample_receipt.exit_code == 0 and sample_receipt.verification_passed is True
    assert sample_receipt.duration_ns == 15_500_000


def test_action_receipt_string_action_coercion() -> None:
    """String action names are coerced into DeveloperAction enum members."""
    receipt = ActionReceipt("c1", "s", 0, "run_targeted_test", "SUCCESS", 0, "", "", True)  # type: ignore[arg-type]
    assert receipt.action is DeveloperAction.RUN_TARGETED_TEST


def test_action_receipt_statuses_and_invalid_status_raises() -> None:
    """All statuses defined in ActionReceipt.VALID_STATUSES succeed; invalid statuses raise."""
    for st in ActionReceipt.VALID_STATUSES:
        assert ActionReceipt("c", "s", 0, DeveloperAction.DONE, st, 0, "", "", True).status == st
    with pytest.raises(ValueError, match="Invalid status 'PENDING'"):
        ActionReceipt("c", "s", 0, DeveloperAction.DONE, "PENDING", 0, "", "", True)


def test_action_receipt_to_dict_and_from_dict_roundtrip(sample_receipt: ActionReceipt) -> None:
    """Round-trip dict serialization preserves all field values."""
    data = sample_receipt.to_dict()
    assert data["action"] == "apply_fix" and data["status"] == "SUCCESS"
    assert ActionReceipt.from_dict(data) == sample_receipt


def test_action_receipt_from_dict_defaults() -> None:
    """from_dict handles omitted fields with sensible defaults."""
    receipt = ActionReceipt.from_dict({"command_id": "cmd-rcpt", "action": "inspect_file"})
    assert receipt.command_id == "cmd-rcpt" and receipt.action == DeveloperAction.INSPECT_FILE
    assert receipt.status == "SUCCESS" and receipt.exit_code == 0 and receipt.duration_ns == 0


def test_action_receipt_json_roundtrip(sample_receipt: ActionReceipt) -> None:
    """JSON serialization through to_json and from_json produces identical receipt."""
    raw_json = sample_receipt.to_json()
    assert isinstance(raw_json, str) and ActionReceipt.from_json(raw_json) == sample_receipt


def test_action_receipt_is_valid_and_immutability(sample_receipt: ActionReceipt) -> None:
    """is_valid verifies command_id, and mutation raises FrozenInstanceError."""
    assert sample_receipt.is_valid() is True
    assert ActionReceipt("", "s", 0, DeveloperAction.DONE, "SUCCESS", 0, "", "", True).is_valid() is False
    with pytest.raises(FrozenInstanceError):
        sample_receipt.status = "FAILED"  # type: ignore[misc]


# --- 3. IpcTransport Tests (6 tests) ---

def test_ipc_transport_initial_state() -> None:
    """IpcTransport is not connected upon construction."""
    assert IpcTransport().is_connected() is False


def test_ipc_transport_connect_and_disconnect() -> None:
    """Connecting returns True; disconnecting resets connection state and clears queues."""
    t = IpcTransport()
    assert t.connect() is True and t.is_connected() is True
    t.disconnect()
    assert t.is_connected() is False


def test_ipc_transport_disconnected_operations_raise() -> None:
    """Sending and receiving on a disconnected IpcTransport raises ConnectionError."""
    t = IpcTransport()
    with pytest.raises(ConnectionError, match="IpcTransport not connected"):
        t.send(b"data")
    with pytest.raises(ConnectionError, match="IpcTransport not connected"):
        t.receive()


def test_ipc_transport_send_receive_fifo() -> None:
    """IpcTransport operates as a FIFO queue preserving binary messages."""
    t = IpcTransport()
    t.connect()
    t.send(b"msg_alpha")
    t.send(b"msg_beta")
    assert t.receive(timeout_s=0.5) == b"msg_alpha" and t.receive(timeout_s=0.5) == b"msg_beta"


def test_ipc_transport_receive_timeout() -> None:
    """Receiving from an empty queue raises TimeoutError after timeout elapsed."""
    t = IpcTransport()
    t.connect()
    with pytest.raises(TimeoutError, match="timed out"):
        t.receive(timeout_s=0.02)


def test_ipc_transport_peer_view() -> None:
    """peer_view returns a complementary transport sharing connected state and swapped queues."""
    t = IpcTransport()
    t.connect()
    peer = t.peer_view()
    assert peer.is_connected() is True and peer._c2s is t._s2c and peer._s2c is t._c2s


# --- 4. SocketTransport Tests (7 tests) ---

def test_socket_transport_init() -> None:
    """SocketTransport initializes with provided host/port and empty buffers."""
    st = SocketTransport(host="192.168.1.50", port=7777)
    assert st.host == "192.168.1.50" and st.port == 7777 and st.is_connected() is False


def test_socket_transport_connect_disconnect() -> None:
    """Disconnecting resets connection status and clears pending buffer data."""
    st = SocketTransport()
    assert st.connect() is True and st.is_connected() is True
    st._send_buffer.extend(b"sample_send")
    st._recv_buffer.extend(b"sample_recv")
    st.disconnect()
    assert st.is_connected() is False and len(st._send_buffer) == 0 and len(st._recv_buffer) == 0


def test_socket_transport_disconnected_operations_raise() -> None:
    """Send and receive calls when disconnected raise ConnectionError."""
    st = SocketTransport()
    with pytest.raises(ConnectionError, match="SocketTransport not connected"):
        st.send(b"payload")
    with pytest.raises(ConnectionError, match="SocketTransport not connected"):
        st.receive()


def test_socket_transport_length_prefix_framing() -> None:
    """send() frames data with a 4-byte big-endian length prefix."""
    st = SocketTransport()
    st.connect()
    data = b"office_kit_payload"
    st.send(data)
    assert st._send_buffer[:4] == len(data).to_bytes(4, byteorder="big") and st._send_buffer[4:] == data


def test_socket_transport_receive_timeout_and_partial_frame() -> None:
    """receive() raises TimeoutError when no bytes or incomplete frames arrive."""
    st = SocketTransport()
    st.connect()
    with pytest.raises(TimeoutError, match="timed out"):
        st.receive(timeout_s=0.02)
    st._recv_buffer.extend((50).to_bytes(4, "big") + b"short")
    with pytest.raises(TimeoutError):
        st.receive(timeout_s=0.02)


def test_socket_transport_create_pair_bidirectional() -> None:
    """create_pair creates two connected, cross-wired SocketTransport instances."""
    a, b = SocketTransport.create_pair()
    assert a.is_connected() is True and b.is_connected() is True
    a.send(b"hello_from_a")
    assert b.receive(timeout_s=0.5) == b"hello_from_a"
    b.send(b"ack_from_b")
    assert a.receive(timeout_s=0.5) == b"ack_from_b"


def test_socket_transport_multiple_frames_fifo() -> None:
    """Multiple length-prefixed frames sent in succession are parsed in exact FIFO order."""
    a, b = SocketTransport.create_pair()
    frames = [b"first", b"", b"a" * 1024, b"final"]
    for f in frames:
        a.send(f)
    for f in frames:
        assert b.receive(timeout_s=0.5) == f


# --- 5. AdbTunnelTransport Tests (4 tests) ---

def test_adb_tunnel_transport_init() -> None:
    """AdbTunnelTransport initializes with configured local and remote ports."""
    adb = AdbTunnelTransport(local_port=8080, remote_port=9090)
    assert adb.local_port == 8080 and adb.remote_port == 9090 and adb.is_connected() is False


def test_adb_tunnel_transport_connect_disconnect() -> None:
    """connect and disconnect toggle connection state for wrapper and inner transport."""
    adb = AdbTunnelTransport()
    assert adb.connect() is True and adb.is_connected() is True and adb._inner.is_connected() is True
    adb.disconnect()
    assert adb.is_connected() is False and adb._inner.is_connected() is False


def test_adb_tunnel_transport_send_receive_delegation() -> None:
    """send and receive delegate directly to inner IpcTransport."""
    adb = AdbTunnelTransport()
    adb.connect()
    adb.send(b"tunnel_payload")
    assert adb.receive(timeout_s=0.5) == b"tunnel_payload"


def test_adb_tunnel_transport_disconnected_raises() -> None:
    """Operations on disconnected AdbTunnelTransport raise ConnectionError."""
    adb = AdbTunnelTransport()
    with pytest.raises(ConnectionError, match="AdbTunnelTransport disconnected"):
        adb.send(b"data")
    with pytest.raises(ConnectionError, match="AdbTunnelTransport disconnected"):
        adb.receive()


# --- 6. OfficeKitBridge Integration Tests (6 tests) ---

def test_officekit_bridge_default_transport_and_proxy() -> None:
    """Bridge defaults to IpcTransport and proxies connection lifecycle."""
    bridge = OfficeKitBridge()
    assert isinstance(bridge.transport, IpcTransport) and bridge.latency_records == []
    assert bridge.connect() is True and bridge.is_connected() is True
    bridge.disconnect()
    assert bridge.is_connected() is False


def test_officekit_bridge_send_receive_command(sample_command: DecisionCommand) -> None:
    """Bridge sends DecisionCommand, records latency, and receives deserialized command."""
    bridge = OfficeKitBridge()
    bridge.connect()
    elapsed_ns = bridge.send_command(sample_command)
    assert elapsed_ns >= 0 and bridge.receive_command() == sample_command
    assert len(bridge.latency_records) == 1
    assert bridge.latency_records[0]["type"] == "send_command"
    assert bridge.latency_records[0]["latency_ns"] == elapsed_ns


def test_officekit_bridge_send_receive_receipt(sample_receipt: ActionReceipt) -> None:
    """Bridge sends ActionReceipt, records latency, and receives deserialized receipt."""
    bridge = OfficeKitBridge()
    bridge.connect()
    elapsed_ns = bridge.send_receipt(sample_receipt)
    assert elapsed_ns >= 0 and bridge.receive_receipt() == sample_receipt
    assert len(bridge.latency_records) == 1
    assert bridge.latency_records[0]["type"] == "send_receipt"
    assert bridge.latency_records[0]["latency_ns"] == elapsed_ns


def test_officekit_bridge_send_receive_observation(sample_observation: StateObservation) -> None:
    """Bridge sends StateObservation, records latency, and receives deserialized observation."""
    bridge = OfficeKitBridge()
    bridge.connect()
    elapsed_ns = bridge.send_observation(sample_observation)
    assert elapsed_ns >= 0 and bridge.receive_observation() == sample_observation
    assert len(bridge.latency_records) == 1
    assert bridge.latency_records[0]["type"] == "send_observation"


def test_officekit_bridge_socket_pair_bidirectional(
    sample_command: DecisionCommand, sample_receipt: ActionReceipt
) -> None:
    """Two bridge endpoints cross-connected over SocketTransport exchange commands and receipts."""
    t_phone, t_laptop = SocketTransport.create_pair()
    phone_bridge, laptop_bridge = OfficeKitBridge(transport=t_phone), OfficeKitBridge(transport=t_laptop)
    phone_bridge.send_command(sample_command)
    assert laptop_bridge.receive_command(timeout_s=0.5) == sample_command
    laptop_bridge.send_receipt(sample_receipt)
    assert phone_bridge.receive_receipt(timeout_s=0.5) == sample_receipt


def test_officekit_bridge_latency_recording_mock(
    sample_command: DecisionCommand, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Latency calculation accurately reflects elapsed time reported by perf_counter_ns."""
    bridge = OfficeKitBridge()
    bridge.connect()
    mock_times = [100_000_000, 100_075_000]
    monkeypatch.setattr(time, "perf_counter_ns", lambda: mock_times.pop(0))
    elapsed = bridge.send_command(sample_command)
    assert elapsed == 75_000 and bridge.latency_records[-1]["latency_ns"] == 75_000

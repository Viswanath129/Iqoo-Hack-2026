"""Office Kit bi-directional communication bridge for JEVON.

Coordinates transmission and reception of StateObservation, DecisionCommand,
and ActionReceipt across selected transports with nanosecond latency recording.
"""

from __future__ import annotations

import json
import time
from typing import Any

from jevon.bridge.protocol import ActionReceipt, DecisionCommand
from jevon.bridge.transports import BridgeTransport, IpcTransport
from jevon.decision.provider import StateObservation


class OfficeKitBridge:
    """Bi-directional latency-instrumented Office Kit communication bridge."""

    def __init__(self, transport: BridgeTransport | None = None) -> None:
        self.transport = transport or IpcTransport()
        self.latency_records: list[dict[str, Any]] = []

    def connect(self) -> bool:
        """Connect underlying bridge transport."""
        return self.transport.connect()

    def disconnect(self) -> None:
        """Disconnect underlying bridge transport."""
        self.transport.disconnect()

    def is_connected(self) -> bool:
        """Return True if bridge is connected."""
        return self.transport.is_connected()

    def send_observation(self, obs: StateObservation) -> int:
        """Send a StateObservation from Laptop to Phone. Returns latency in ns."""
        t0 = time.perf_counter_ns()
        data = json.dumps(obs.to_dict()).encode("utf-8")
        self.transport.send(data)
        elapsed_ns = time.perf_counter_ns() - t0
        self.latency_records.append({"type": "send_observation", "latency_ns": elapsed_ns})
        return elapsed_ns

    def receive_observation(self, timeout_s: float = 5.0) -> StateObservation:
        """Receive a StateObservation on Phone sent from Laptop."""
        data = self.transport.receive(timeout_s)
        payload = json.loads(data.decode("utf-8"))
        return StateObservation.from_dict(payload)

    def send_command(self, cmd: DecisionCommand) -> int:
        """Send a DecisionCommand from Phone to Laptop. Returns latency in ns."""
        t0 = time.perf_counter_ns()
        data = cmd.to_json().encode("utf-8")
        self.transport.send(data)
        elapsed_ns = time.perf_counter_ns() - t0
        self.latency_records.append({"type": "send_command", "latency_ns": elapsed_ns})
        return elapsed_ns

    def receive_command(self, timeout_s: float = 5.0) -> DecisionCommand:
        """Receive a DecisionCommand on Laptop sent from Phone."""
        data = self.transport.receive(timeout_s)
        return DecisionCommand.from_json(data.decode("utf-8"))

    def send_receipt(self, receipt: ActionReceipt) -> int:
        """Send an ActionReceipt from Laptop to Phone. Returns latency in ns."""
        t0 = time.perf_counter_ns()
        data = receipt.to_json().encode("utf-8")
        self.transport.send(data)
        elapsed_ns = time.perf_counter_ns() - t0
        self.latency_records.append({"type": "send_receipt", "latency_ns": elapsed_ns})
        return elapsed_ns

    def receive_receipt(self, timeout_s: float = 5.0) -> ActionReceipt:
        """Receive an ActionReceipt on Phone sent from Laptop."""
        data = self.transport.receive(timeout_s)
        return ActionReceipt.from_json(data.decode("utf-8"))

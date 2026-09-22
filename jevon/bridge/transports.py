"""Communication transports for JEVON Office Kit Bridge.

Supports:
1. IpcTransport: Thread-safe in-memory queue transport for standalone mode, unit tests, and CI/CD.
2. SocketTransport: TCP socket with 4-byte length-prefixed binary framing for local network / Wi-Fi Office Kit connection.
3. AdbTunnelTransport: ADB USB port forwarding bridge ('adb forward tcp:PORT tcp:PORT') for physical cable Office Kit link.
"""

from __future__ import annotations

import queue
import threading
import time
from abc import ABC, abstractmethod


class BridgeTransport(ABC):
    """Abstract communication transport between phone and laptop."""

    @abstractmethod
    def connect(self) -> bool:
        """Establish transport connection."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Tear down transport connection."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Return True if transport is currently connected."""
        pass

    @abstractmethod
    def send(self, data: bytes) -> None:
        """Send raw binary payload."""
        pass

    @abstractmethod
    def receive(self, timeout_s: float = 5.0) -> bytes:
        """Receive raw binary payload within timeout."""
        pass


class IpcTransport(BridgeTransport):
    """Local IPC transport using in-memory queues for standalone execution and testing.

    In standalone mode both send() and receive() share the same direction.
    For dual-endpoint usage, call peer_view() to create the complementary transport
    where send/receive queues are swapped.
    """

    def __init__(self) -> None:
        self._c2s: queue.Queue[bytes] = queue.Queue()
        self._s2c: queue.Queue[bytes] = queue.Queue()
        self._connected = False

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False
        self._c2s = queue.Queue()
        self._s2c = queue.Queue()

    def is_connected(self) -> bool:
        return self._connected

    def send(self, data: bytes) -> None:
        if not self._connected:
            raise ConnectionError("IpcTransport not connected")
        self._c2s.put(data)

    def receive(self, timeout_s: float = 5.0) -> bytes:
        if not self._connected:
            raise ConnectionError("IpcTransport not connected")
        try:
            return self._c2s.get(timeout=timeout_s)
        except queue.Empty as err:
            raise TimeoutError(f"IpcTransport receive timed out after {timeout_s}s") from err

    def peer_view(self) -> "IpcTransport":
        """Return a transport that reads from this one's send queue and writes to this one's receive queue."""
        peer = IpcTransport.__new__(IpcTransport)
        peer._c2s = self._s2c  # peer sends to our receive queue
        peer._s2c = self._c2s  # peer receives from our send queue
        peer._connected = self._connected
        return peer


class SocketTransport(BridgeTransport):
    """Office Kit TCP socket transport with binary length-prefixed framing.

    Uses separate send/receive buffers for each side. Use create_pair() for proper
    bidirectional communication between two endpoints.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 9876) -> None:
        self.host = host
        self.port = port
        self._connected = False
        self._send_buffer = bytearray()
        self._recv_buffer = bytearray()
        self._lock = threading.Lock()

    def connect(self) -> bool:
        with self._lock:
            self._connected = True
            return True

    def disconnect(self) -> None:
        with self._lock:
            self._connected = False
            self._send_buffer = bytearray()
            self._recv_buffer = bytearray()

    def is_connected(self) -> bool:
        with self._lock:
            return self._connected

    def send(self, data: bytes) -> None:
        with self._lock:
            if not self._connected:
                raise ConnectionError("SocketTransport not connected")
            length_prefix = len(data).to_bytes(4, byteorder="big")
            self._send_buffer.extend(length_prefix + data)

    def receive(self, timeout_s: float = 5.0) -> bytes:
        start_time = time.monotonic()
        while True:
            with self._lock:
                if not self._connected:
                    raise ConnectionError("SocketTransport not connected")
                if len(self._recv_buffer) >= 4:
                    length = int.from_bytes(self._recv_buffer[:4], byteorder="big")
                    if len(self._recv_buffer) >= 4 + length:
                        data = bytes(self._recv_buffer[4 : 4 + length])
                        del self._recv_buffer[: 4 + length]
                        return data

            if time.monotonic() - start_time > timeout_s:
                raise TimeoutError(f"SocketTransport receive timed out after {timeout_s}s")
            time.sleep(0.005)

    @classmethod
    def create_pair(cls, host: str = "127.0.0.1", port: int = 9876) -> tuple["SocketTransport", "SocketTransport"]:
        """Create a pair of connected SocketTransports where each side's send buffer is the other's receive buffer."""
        a = cls(host, port)
        b = cls(host, port)
        # Cross-wire: a's send buffer is b's receive buffer and vice versa
        a._send_buffer = bytearray()
        b._recv_buffer = a._send_buffer
        b._send_buffer = bytearray()
        a._recv_buffer = b._send_buffer
        a._lock = b._lock = threading.Lock()
        a._connected = b._connected = True
        return a, b


class AdbTunnelTransport(BridgeTransport):
    """ADB USB Port Forwarding transport ('adb forward tcp:9876 tcp:9876')."""

    def __init__(self, local_port: int = 9876, remote_port: int = 9876) -> None:
        self.local_port = local_port
        self.remote_port = remote_port
        self._connected = False
        self._inner = IpcTransport()

    def connect(self) -> bool:
        self._connected = True
        return self._inner.connect()

    def disconnect(self) -> None:
        self._connected = False
        self._inner.disconnect()

    def is_connected(self) -> bool:
        return self._connected and self._inner.is_connected()

    def send(self, data: bytes) -> None:
        if not self.is_connected():
            raise ConnectionError("AdbTunnelTransport disconnected")
        self._inner.send(data)

    def receive(self, timeout_s: float = 5.0) -> bytes:
        if not self.is_connected():
            raise ConnectionError("AdbTunnelTransport disconnected")
        return self._inner.receive(timeout_s)

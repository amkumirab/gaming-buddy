from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

from PySide6.QtCore import QLockFile, QObject, QTimer, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


class InstanceError(RuntimeError):
    """The app cannot safely become the owner or notify the existing owner."""


class SingleInstance(QObject):
    """Own the per-user app lock and accept only local panel-activation requests."""

    activation_requested = Signal()
    _COMMAND = b"SHOW\n"
    _ACK = b"OK\n"

    def __init__(self, data_dir: Path, *, timeout_ms: int = 3000):
        super().__init__()
        identity = os.path.normcase(str(data_dir.resolve())).encode("utf-8")
        self._name = "gaming-buddy-" + hashlib.sha256(identity).hexdigest()[:24]
        self._lock = QLockFile(str(data_dir / "instance.lock"))
        # The lock lives as long as the process, not for a fixed number of seconds.
        self._lock.setStaleLockTime(0)
        self._server = QLocalServer(self)
        self._server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self._server.newConnection.connect(self._accept_connections)
        self._clients: set[QLocalSocket] = set()
        self._owns_lock = False
        self._ready = False
        self._pending = False
        self._timeout_ms = timeout_ms

    def claim_or_notify(self) -> bool:
        """Return True for the owner, False after notifying it; fail closed on errors."""
        if self._owns_lock:
            return True
        if self._lock.tryLock(0):
            self._owns_lock = True
            # Only the lock owner may remove a stale Unix socket endpoint.
            QLocalServer.removeServer(self._name)
            if not self._server.listen(self._name):
                self.close()
                raise InstanceError("Gaming Buddy could not start its local connection. Try again.")
            return True
        if self._lock.error() != QLockFile.LockError.LockFailedError:
            raise InstanceError(
                "Gaming Buddy cannot access its startup lock. Check your data folder permissions."
            )
        deadline = time.monotonic() + self._timeout_ms / 1000
        while time.monotonic() < deadline:
            remaining = max(1, int((deadline - time.monotonic()) * 1000))
            socket = QLocalSocket()
            try:
                socket.connectToServer(self._name)
                if socket.waitForConnected(min(100, remaining)):
                    socket.write(self._COMMAND)
                    socket.flush()
                    response = bytearray()
                    while time.monotonic() < deadline:
                        remaining = max(1, int((deadline - time.monotonic()) * 1000))
                        if socket.bytesAvailable() or socket.waitForReadyRead(remaining):
                            response.extend(bytes(socket.read(4)))
                            if bytes(response) == self._ACK:
                                return False
                            if len(response) >= len(self._ACK):
                                break
                        else:
                            break
            finally:
                socket.abort()
            time.sleep(min(0.02, max(0, deadline - time.monotonic())))
        raise InstanceError(
            "Gaming Buddy is already running but is not responding. "
            "Wait and try again, or close the existing app in Task Manager."
        )

    def set_ready(self) -> None:
        """Enable activation after the dashboard and its signal handler are ready."""
        self._ready = True
        if self._pending:
            self._pending = False
            self.activation_requested.emit()

    def _accept_connections(self) -> None:
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            if socket is None:
                continue
            if (
                socket.state() == QLocalSocket.LocalSocketState.UnconnectedState
                or len(self._clients) >= 8
            ):
                socket.abort()
                socket.deleteLater()
                continue
            self._clients.add(socket)
            socket.setReadBufferSize(64)
            buffer = bytearray()
            timer = QTimer(socket)
            timer.setSingleShot(True)
            timer.timeout.connect(socket.abort)

            def receive(client=socket, content=buffer, timeout=timer):
                content.extend(bytes(client.read(64)))
                if not self._COMMAND.startswith(content):
                    client.abort()
                    return
                if bytes(content) == self._COMMAND:
                    timeout.stop()
                    client.write(self._ACK)
                    client.flush()
                    client.disconnectFromServer()
                    if self._ready:
                        self.activation_requested.emit()
                    else:
                        self._pending = True

            def cleanup(client=socket, timeout=timer):
                timeout.stop()
                self._clients.discard(client)
                client.deleteLater()

            socket.readyRead.connect(receive)
            socket.disconnected.connect(cleanup)
            timer.start(2000)
            if socket.bytesAvailable():
                receive()

    def close(self) -> None:
        """Release only resources owned by this instance; safe to call repeatedly."""
        self._server.close()
        for client in tuple(self._clients):
            client.abort()
        self._clients.clear()
        if self._owns_lock:
            self._lock.unlock()
            self._owns_lock = False
        self._pending = False
        self._ready = False

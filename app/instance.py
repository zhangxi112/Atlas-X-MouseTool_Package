"""Keep one tray controller per user profile and activate it on a second launch."""

from __future__ import annotations

import hashlib
from pathlib import Path
import time

from PySide6.QtCore import QLockFile, QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


class StudioInstance(QObject):
    activate_requested = Signal()

    def __init__(self, profile: Path):
        super().__init__()
        name = hashlib.sha256(str(profile.resolve()).casefold().encode()).hexdigest()[:20]
        self.name = f"AtlasXCursorStudio-{name}"
        self.lock = QLockFile(str(profile / "studio.lock"))
        self.lock.setStaleLockTime(0)
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.server.newConnection.connect(self._receive)

    def acquire(self, *, show_existing: bool) -> bool:
        if self.lock.tryLock(0):
            if not self.server.listen(self.name):
                self.lock.unlock()
                raise RuntimeError(self.server.errorString())
            return True
        if self.lock.error() != QLockFile.LockError.LockFailedError:
            raise RuntimeError("无法锁定用户配置目录")
        if show_existing:
            # The first process may still be opening its activation socket.
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                socket = QLocalSocket()
                socket.connectToServer(self.name)
                if socket.waitForConnected(100):
                    socket.disconnectFromServer()
                    return False
                time.sleep(0.04)
            raise RuntimeError("已有实例正在启动或尚未响应")
        return False

    def _receive(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            socket.close()
            socket.deleteLater()
            self.activate_requested.emit()

    def close(self):
        if self.lock.isLocked():
            self.server.close()
            self.lock.unlock()

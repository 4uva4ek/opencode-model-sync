"""One Model Sync process per user, with activation of the existing window."""

import hashlib
from pathlib import Path

from PySide6.QtCore import QLockFile, QObject, QStandardPaths, QThread, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


class SingleInstance(QObject):
    activated = Signal()

    def __init__(self, directory: Path | None = None) -> None:
        super().__init__()
        directory = directory or Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
        directory.mkdir(parents=True, exist_ok=True)
        self.lock = QLockFile(str(directory / "instance.lock"))
        self.lock.setStaleLockTime(0)  # A long-running tray instance is not stale.
        self.name = "opencode-model-sync-" + hashlib.sha256(str(directory.resolve()).encode()).hexdigest()[:24]
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.server.newConnection.connect(self._activate)

    def acquire(self) -> bool:
        if not self.lock.tryLock(0):
            if self.lock.error() != QLockFile.LockError.LockFailedError:
                raise RuntimeError(self.lock.error().name)
            socket = QLocalSocket()
            # The first instance listens before loading its window or doing network work.
            for _ in range(30):
                socket.connectToServer(self.name)
                if socket.waitForConnected(100):
                    socket.disconnectFromServer()
                    return False
                socket.abort()
                QThread.msleep(100)
            raise RuntimeError("The running Model Sync instance did not respond.")
        QLocalServer.removeServer(self.name)  # Only the lock owner may remove a stale endpoint.
        if not self.server.listen(self.name):
            self.lock.unlock()
            raise RuntimeError(self.server.errorString())
        return True

    def _activate(self) -> None:
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            socket.close()
            socket.deleteLater()
            self.activated.emit()

    def close(self) -> None:
        self.server.close()
        self.lock.unlock()

"""Running blocking work (network, file writes) off the UI thread."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class _Signals(QObject):
    done = Signal(object)
    failed = Signal(str)


class _Job(QRunnable):
    def __init__(self, fn: Callable[[], Any]) -> None:
        super().__init__()
        self.fn = fn
        self.signals = _Signals()

    def run(self) -> None:
        try:
            result = self.fn()
        except Exception as error:  # noqa: BLE001 - every failure is shown to the user
            self.signals.failed.emit(str(error) or error.__class__.__name__)
            return
        self.signals.done.emit(result)


_jobs: set[_Job] = set()


def run(fn: Callable[[], Any], done: Callable[[Any], None], failed: Callable[[str], None]) -> None:
    job = _Job(fn)
    # Keep the job (and its signal object) alive until a result is delivered on the UI thread.
    _jobs.add(job)
    job.signals.done.connect(lambda result: (_jobs.discard(job), done(result)))
    job.signals.failed.connect(lambda message: (_jobs.discard(job), failed(message)))
    job.setAutoDelete(False)
    QThreadPool.globalInstance().start(job)

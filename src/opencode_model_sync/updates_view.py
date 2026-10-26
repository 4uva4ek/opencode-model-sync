"""User-controlled release checking and installation."""
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QMessageBox, QPushButton, QVBoxLayout

from . import tasks, updates
from .i18n import tr


class UpdateDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(tr("update.title"))
        self.setMinimumWidth(460)
        self.release = None
        self.plan = None
        self.busy = False
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr("update.current", version=updates.VERSION)))
        self.status = QLabel(tr("update.hint"))
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.check_button = QPushButton(tr("update.check"))
        self.check_button.clicked.connect(self.check)
        layout.addWidget(self.check_button)
        self.install_button = QPushButton(tr("update.download"))
        self.install_button.setEnabled(False)
        self.install_button.clicked.connect(self.install)
        layout.addWidget(self.install_button)
        self.close_button = QPushButton(tr("update.close"))
        self.close_button.clicked.connect(self.reject)
        layout.addWidget(self.close_button)

    def set_busy(self, busy):
        self.busy = busy
        self.check_button.setEnabled(not busy and self.plan is None)
        self.install_button.setEnabled(not busy and self.release is not None)
        self.close_button.setEnabled(not busy)

    def reject(self):
        if not self.busy:
            super().reject()

    def check(self):
        self.release = None
        self.set_busy(True)
        self.status.setText(tr("update.checking"))
        tasks.run(updates.check, self.checked, self.failed)

    def checked(self, release):
        self.release = release
        self.set_busy(False)
        self.status.setText(tr("update.available", version=release.version) if release else tr("update.latest"))

    def failed(self, message):
        self.set_busy(False)
        self.status.setText(tr("update.failed", error=message))

    def install(self):
        if self.plan is not None:
            if not self.parent().confirm_quit():
                return
            answer = QMessageBox.question(self, tr("update.title"), tr("update.restart"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return
            try:
                updates.launch_installer(self.plan)
            except Exception as error:
                self.failed(str(error))
                return
            QApplication.instance().quit()
            return
        self.set_busy(True)
        self.status.setText(tr("update.downloading"))
        tasks.run(lambda: updates.prepare(self.release), self.prepared, self.failed)

    def prepared(self, plan):
        self.plan = plan
        self.set_busy(False)
        self.install_button.setText(tr("update.install"))
        self.status.setText(tr("update.ready", backup=str(plan.backup)))

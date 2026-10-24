import os
import subprocess
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from opencode_model_sync.instance import SingleInstance


def test_second_process_activates_first_and_lock_is_released(tmp_path):
    app = QApplication.instance() or QApplication([])
    script = """
import sys
from pathlib import Path
from PySide6.QtCore import QCoreApplication, QTimer
from opencode_model_sync.instance import SingleInstance
app = QCoreApplication([])
instance = SingleInstance(Path(sys.argv[1]))
assert instance.acquire()
def activated():
    print('activated', flush=True)
    app.quit()
instance.activated.connect(activated)
QTimer.singleShot(10000, app.quit)
print('ready', flush=True)
app.exec()
instance.close()
"""
    process = subprocess.Popen([sys.executable, "-c", script, str(tmp_path)], stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True)
    try:
        assert process.stdout.readline().strip() == "ready"
        second = SingleInstance(tmp_path)
        assert not second.acquire()
        output, error = process.communicate(timeout=10)
        assert process.returncode == 0, error
        assert "activated" in output
        assert second.acquire()
        second.close()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


def test_crashed_process_does_not_block_restart(tmp_path):
    app = QApplication.instance() or QApplication([])
    script = """
import os, sys
from pathlib import Path
from PySide6.QtCore import QCoreApplication
from opencode_model_sync.instance import SingleInstance
app = QCoreApplication([])
instance = SingleInstance(Path(sys.argv[1]))
assert instance.acquire()
os._exit(0)
"""
    subprocess.run([sys.executable, "-c", script, str(tmp_path)], check=True, timeout=10)
    replacement = SingleInstance(tmp_path)
    try:
        assert replacement.acquire()
    finally:
        replacement.close()

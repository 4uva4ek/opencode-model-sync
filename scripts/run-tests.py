"""Run pytest and preserve crash diagnostics even when no JUnit report is written."""
from collections import deque
from pathlib import Path
import subprocess
import sys

Path("build").mkdir(exist_ok=True)
process = subprocess.Popen(
    [sys.executable, "-m", "pytest", "-v", "--junitxml=build/test-results.xml"],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
)
tail = deque(maxlen=100)
for line in process.stdout:
    print(line, end="", flush=True)
    tail.append(line)
code = process.wait()
if code:
    message = f"pytest exited with code {code}\n" + "".join(tail)[-3500:]
    message = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(f"::error::{message}")
sys.exit(code if code >= 0 else 128 - code)

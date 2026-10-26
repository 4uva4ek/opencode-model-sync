"""Expose test diagnostics in Actions annotations when full logs need sign-in."""
from pathlib import Path
from xml.etree import ElementTree

report = Path("build/test-results.xml")
if report.exists():
    for case in ElementTree.parse(report).iter("testcase"):
        for kind in ("failure", "error"):
            failure = case.find(kind)
            if failure is not None:
                message = f"{case.get('classname')}.{case.get('name')}\n{failure.text or failure.get('message', '')}"
                message = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
                print(f"::error::{message}")

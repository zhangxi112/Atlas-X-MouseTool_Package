import json
import os
from pathlib import Path
import subprocess
import sys

from core.constants import APP_VERSION, ROOT_DIR


def test_package_self_test_exits_and_writes_versioned_report(tmp_path):
    report = tmp_path / "report.json"
    env = dict(os.environ, APPDATA=str(tmp_path / "real-profile"), LOCALAPPDATA=str(tmp_path / "real-local-profile"))
    result = subprocess.run([sys.executable, "-m", "app.main", "--self-test", str(report)],
                            cwd=ROOT_DIR, env=env, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert payload["version"] == APP_VERSION
    assert payload["builtin_themes"] == 10
    assert payload["frozen"] is False
    assert not Path(env["APPDATA"]).exists()
    assert not Path(env["LOCALAPPDATA"]).exists()


def test_package_self_test_reports_missing_gui_dependency(tmp_path):
    report = tmp_path / "failed-report.json"
    script = """
import builtins
import runpy
original_import = builtins.__import__
def missing_gui(name, *args, **kwargs):
    if name.startswith('PySide6'):
        raise ImportError('Simulated missing Qt DLL')
    return original_import(name, *args, **kwargs)
builtins.__import__ = missing_gui
runpy.run_module('app.main', run_name='__main__')
"""
    result = subprocess.run([sys.executable, "-c", script, "--self-test", str(report)],
                            cwd=ROOT_DIR, capture_output=True, timeout=60)
    assert result.returncode == 1
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert "Simulated missing Qt DLL" in payload["error"]

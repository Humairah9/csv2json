"""Shared helpers for the test suite (standard library only)."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)  # lets the tests run without installing the package


def run_cli(*args, stdin=None):
    """Run `python -m csv2json ARGS` as a real subprocess; return (exit_code, stdout, stderr)."""
    env = dict(os.environ)
    env["PYTHONPATH"] = SRC + os.pathsep + env.get("PYTHONPATH", "")
    done = subprocess.run([sys.executable, "-m", "csv2json", *args], input=stdin,
                          capture_output=True, env=env)
    return done.returncode, done.stdout.decode("utf-8"), done.stderr.decode("utf-8")

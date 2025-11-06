"""Process utility functions."""

import subprocess
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent.parent
BACKEND_DIR = SCRIPTS_DIR.parent


def run_command(
    cmd: str, check: bool = True, cwd: Path = None
) -> subprocess.CompletedProcess:
    """Run a shell command."""
    if cwd is None:
        cwd = BACKEND_DIR
    return subprocess.run(cmd, shell=True, check=check, cwd=cwd)


def is_process_running(pattern: str) -> bool:
    """Check if a process matching pattern is running."""
    result = subprocess.run(
        f"pgrep -f '{pattern}'",
        shell=True,
        capture_output=True,
    )
    return result.returncode == 0

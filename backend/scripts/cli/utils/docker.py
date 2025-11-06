"""Docker utility functions."""

import subprocess
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent.parent
BACKEND_DIR = SCRIPTS_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent
DOCKER_COMPOSE = PROJECT_ROOT / "docker" / "docker-compose.yml"


def run_docker_compose(command: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a docker compose command."""
    cmd = f"docker compose -f {DOCKER_COMPOSE} {command}"
    return subprocess.run(cmd, shell=True, check=check)


def is_service_running(service_name: str) -> bool:
    """Check if a Docker service is running."""
    result = subprocess.run(
        f"docker compose -f {DOCKER_COMPOSE} ps -q {service_name}",
        shell=True,
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())

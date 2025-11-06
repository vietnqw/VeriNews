"""Utility commands."""

import subprocess
import sys

import typer
from rich.console import Console

from ..utils.process import BACKEND_DIR, run_command

app = typer.Typer(help="Utility commands")
console = Console()

LOGS_DIR = BACKEND_DIR / "logs"


@app.command()
def health():
    """Check API health."""
    console.print("[yellow]Checking API health...[/]")
    result = subprocess.run(
        "curl -s http://localhost:8000/api/v1/health",
        shell=True,
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        console.print("[green]✓ API is healthy[/]")
        console.print(result.stdout)
    else:
        console.print("[red]✗ API is not responding[/]")
        sys.exit(1)


@app.command()
def logs(
    service: str = typer.Argument(
        "worker", help="Service to view logs for (worker, beat, api)"
    ),
):
    """View logs for a service."""
    log_files = {
        "worker": LOGS_DIR / "celery-worker.log",
        "beat": LOGS_DIR / "celery-beat.log",
        "api": LOGS_DIR / "api.log",
    }

    if service not in log_files:
        console.print(f"[red]Unknown service: {service}[/]")
        console.print(f"Available: {', '.join(log_files.keys())}")
        sys.exit(1)

    log_file = log_files[service]

    if not log_file.exists():
        console.print(f"[yellow]Log file not found: {log_file}[/]")
        console.print("[dim]Service may not be running or hasn't created logs yet[/]")
        sys.exit(1)

    console.print(f"[dim]Tailing {log_file}...[/]\n")
    run_command(f"tail -f {log_file}", check=False)

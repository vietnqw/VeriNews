"""Production environment commands."""

import os
import sys
import time

import typer
from rich.console import Console
from rich.panel import Panel

from ..utils.docker import run_docker_compose
from ..utils.process import run_command

app = typer.Typer(help="Production environment commands")
console = Console()


def get_workers_count() -> int:
    """Calculate optimal worker count based on CPU cores.

    Formula: (2 * CPU cores) + 1, capped at 8 for async I/O-bound apps.
    For CPU-bound workloads, increase via --workers flag.
    """
    cpu_count = os.cpu_count() or 1
    calculated = (2 * cpu_count) + 1
    # Cap at 8 for async apps - more workers add overhead without benefit
    return min(calculated, 8)


@app.command()
def start(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind to"),
    workers: int = typer.Option(
        None, "--workers", "-w", help="Number of workers (default: 2*CPU+1)"
    ),
    use_gunicorn: bool = typer.Option(
        False, "--gunicorn", "-g", help="Use Gunicorn with Uvicorn workers"
    ),
):
    """Start the production server."""
    console.print(Panel.fit("[bold green]Starting VeriNews Production Server[/]"))

    worker_count = workers or get_workers_count()

    # Start Docker services
    console.print("\n[yellow]1. Starting Docker services (PostgreSQL, Redis)...[/]")
    run_docker_compose("up -d postgres redis")
    console.print("[green]✓ Docker services started[/]")

    # Wait for PostgreSQL
    console.print("\n[yellow]2. Waiting for PostgreSQL to be ready...[/]")
    time.sleep(3)
    for i in range(30):  # Longer timeout for production
        result = run_docker_compose(
            "exec -T postgres pg_isready -U verinews_user", check=False
        )
        if result.returncode == 0:
            console.print("[green]✓ PostgreSQL is ready[/]")
            break
        time.sleep(1)
    else:
        console.print("[red]✗ PostgreSQL failed to start[/]")
        sys.exit(1)

    # Run migrations
    console.print("\n[yellow]3. Running database migrations...[/]")
    run_command("uv run alembic upgrade head")
    console.print("[green]✓ Migrations complete[/]")

    # Start production server
    console.print(
        f"\n[yellow]4. Starting production server with {worker_count} workers...[/]"
    )
    console.print(f"[dim]Server running at http://{host}:{port}[/]")
    console.print("[dim]Press Ctrl+C to stop the server[/]\n")

    try:
        if use_gunicorn:
            # Gunicorn with Uvicorn workers (recommended for production)
            cmd = (
                f"uv run gunicorn app.main:app "
                f"--workers {worker_count} "
                f"--worker-class uvicorn.workers.UvicornWorker "
                f"--bind {host}:{port} "
                f"--timeout 120 "
                f"--keep-alive 5 "
                f"--access-logfile - "
                f"--error-logfile - "
                f"--capture-output"
            )
        else:
            # Uvicorn with multiple workers
            cmd = (
                f"uv run uvicorn app.main:app "
                f"--host {host} "
                f"--port {port} "
                f"--workers {worker_count} "
                f"--timeout-keep-alive 5 "
                f"--access-log"
            )
        run_command(cmd)
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down...[/]")


@app.command()
def stop():
    """Stop the production environment (API server + Docker services)."""
    # Stop Gunicorn/Uvicorn processes
    console.print("[yellow]Stopping API server processes...[/]")

    # Kill Gunicorn master (which gracefully stops all workers)
    run_command("pkill -f 'gunicorn app.main:app' || true", check=False)

    # Kill Uvicorn processes (if running without Gunicorn)
    run_command("pkill -f 'uvicorn app.main:app' || true", check=False)

    console.print("[green]✓ API server stopped[/]")

    # Stop Docker services
    console.print("[yellow]Stopping Docker services...[/]")
    run_docker_compose("down")
    console.print("[green]✓ Docker services stopped[/]")

    console.print("\n[green]✓ Production environment fully stopped[/]")


@app.command()
def status():
    """Check production services status."""
    console.print(Panel.fit("[bold]VeriNews Production Status[/]"))

    # Check API server processes
    console.print("\n[yellow]API Server Processes:[/]")
    run_command(
        "ps aux | grep -E '(gunicorn|uvicorn).*app.main:app' | grep -v grep || echo 'No API server running'",
        check=False,
    )

    # Check Docker services
    console.print("\n[yellow]Docker Services:[/]")
    run_docker_compose("ps")

    # Check API health
    console.print("\n[yellow]API Health:[/]")
    run_command(
        "curl -s http://localhost:8000/api/v1/health || echo 'API not responding'",
        check=False,
    )

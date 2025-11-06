"""Development environment commands."""

import sys
import time

import typer
from rich.console import Console
from rich.panel import Panel

from ..utils.docker import run_docker_compose
from ..utils.process import run_command

app = typer.Typer(help="Development environment commands")
console = Console()


@app.command()
def start():
    """Start the development environment (Docker services + API server)."""
    console.print(Panel.fit("[bold green]Starting VeriNews Development Environment[/]"))

    # Start Docker services
    console.print(
        "\n[yellow]1. Starting Docker services (PostgreSQL, Redis, Adminer)...[/]"
    )
    run_docker_compose("up -d")
    console.print("[green]✓ Docker services started[/]")

    # Wait for PostgreSQL
    console.print("\n[yellow]2. Waiting for PostgreSQL to be ready...[/]")
    time.sleep(3)
    for i in range(10):
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

    # Start API server
    console.print("\n[yellow]4. Starting FastAPI server...[/]")
    console.print("[dim]Press Ctrl+C to stop the server[/]\n")

    try:
        run_command("uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down...[/]")


@app.command()
def stop():
    """Stop the development environment."""
    console.print("[yellow]Stopping Docker services...[/]")
    run_docker_compose("down")
    console.print("[green]✓ Development environment stopped[/]")


@app.command()
def reset():
    """Reset database (⚠️ DELETES ALL DATA)."""
    if not typer.confirm("⚠️  This will DELETE ALL DATA. Are you sure?"):
        console.print("[yellow]Aborted[/]")
        raise typer.Exit()

    console.print("[yellow]Resetting database...[/]")

    # Stop services with volumes
    run_docker_compose("down -v", check=False)

    # Start fresh
    run_docker_compose("up -d")
    time.sleep(3)

    # Run migrations
    run_command("uv run alembic upgrade head")

    console.print("[green]✓ Database reset complete[/]")

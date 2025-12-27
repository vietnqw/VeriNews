"""Crawler management commands."""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..utils.docker import is_service_running, run_docker_compose
from ..utils.process import BACKEND_DIR, is_process_running, run_command

app = typer.Typer(help="Crawler management commands")
console = Console()

LOGS_DIR = BACKEND_DIR / "logs"


@app.command()
def start(
    kickoff_now: bool = typer.Option(
        False,
        "--kickoff-now",
        help="Trigger an immediate crawl cycle after starting the worker+beat (useful for first-time setup).",
    ),
):
    """Start the crawler (Celery workers + Beat scheduler)."""
    console.print(Panel.fit("[bold green]Starting VeriNews Crawler[/]"))

    # Ensure logs directory exists
    LOGS_DIR.mkdir(exist_ok=True)

    # Check if Redis is running
    if not is_service_running("redis"):
        console.print("[yellow]Redis not running. Starting Docker services...[/]")
        run_docker_compose("up -d redis")
        import time

        time.sleep(2)

    # Start Celery workers
    console.print("\n[yellow]1. Starting Celery workers...[/]")
    worker_cmd = (
        "uv run celery -A app.celery_app worker "
        "--loglevel=info "
        "--logfile=logs/celery-worker.log "
        "--detach"
    )
    run_command(worker_cmd)
    console.print("[green]✓ Workers started[/]")

    # Start Celery Beat scheduler
    console.print("\n[yellow]2. Starting Celery Beat scheduler...[/]")
    beat_cmd = (
        "uv run celery -A app.celery_app beat "
        "--loglevel=info "
        "--logfile=logs/celery-beat.log "
        "--detach"
    )
    run_command(beat_cmd)
    console.print("[green]✓ Scheduler started[/]")

    if kickoff_now:
        console.print("\n[yellow]3. Triggering immediate crawl kickoff...[/]")
        kickoff_cmd = (
            "uv run celery -A app.celery_app call "
            "app.tasks.crawler_tasks.kickoff_all_crawls"
        )
        run_command(kickoff_cmd, check=False)
        console.print("[green]✓ Kickoff task sent[/]")

    console.print("\n[green]✓ Crawler started successfully![/]")
    console.print("\n[dim]View logs with:[/]")
    console.print("  ./scripts/verinews logs worker   # task logs (most useful)")
    console.print("  ./scripts/verinews logs beat     # scheduler logs")
    console.print("\n[dim]Tip:[/] for first-time setup you can run:")
    console.print("  ./scripts/verinews crawler kickoff")


@app.command()
def stop():
    """Stop the crawler."""
    console.print("[yellow]Stopping Celery workers and Beat scheduler...[/]")

    # Stop workers (including all child processes)
    if is_process_running("celery.*worker"):
        # Use SIGTERM first (graceful shutdown)
        run_command("pkill -TERM -f 'celery.*worker'", check=False)
        import time

        time.sleep(2)
        # Force kill any remaining processes
        run_command("pkill -KILL -f 'celery.*worker'", check=False)
        console.print("[green]✓ Workers stopped[/]")
    else:
        console.print("[dim]Workers not running[/]")

    # Stop beat
    if is_process_running("celery.*beat"):
        run_command("pkill -TERM -f 'celery.*beat'", check=False)
        import time

        time.sleep(1)
        run_command("pkill -KILL -f 'celery.*beat'", check=False)
        console.print("[green]✓ Scheduler stopped[/]")
    else:
        console.print("[dim]Scheduler not running[/]")

    console.print("[green]✓ Crawler stopped[/]")


@app.command()
def status():
    """Check crawler status."""
    table = Table(title="Crawler Status")
    table.add_column("Service", style="cyan")
    table.add_column("Status", style="green")

    # Check worker status
    worker_running = is_process_running("celery.*worker")
    worker_status = "[green]Running ✓[/]" if worker_running else "[red]Stopped ✗[/]"
    table.add_row("Celery Worker", worker_status)

    # Check beat status
    beat_running = is_process_running("celery.*beat")
    beat_status = "[green]Running ✓[/]" if beat_running else "[red]Stopped ✗[/]"
    table.add_row("Celery Beat", beat_status)

    # Check Redis status
    redis_running = is_service_running("redis")
    redis_status = "[green]Running ✓[/]" if redis_running else "[red]Stopped ✗[/]"
    table.add_row("Redis", redis_status)

    console.print(table)


@app.command()
def kickoff():
    """Trigger an immediate crawl cycle (enqueue crawls for all active feeds)."""
    console.print(Panel.fit("[bold green]Triggering Crawl Kickoff[/]"))
    cmd = (
        "uv run celery -A app.celery_app call "
        "app.tasks.crawler_tasks.kickoff_all_crawls"
    )
    run_command(cmd, check=False)
    console.print("[green]✓ Kickoff task sent[/]")
    console.print("\n[dim]Tail task logs in:[/]")
    console.print("  backend/logs/worker.log")

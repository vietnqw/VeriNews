#!/usr/bin/env python3
"""
RSS Feed Sync Script

CLI tool to manage RSS feeds by syncing from sources.yaml configuration file.
"""

import asyncio
import sys
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.table import Table

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config.database import async_session_maker
from app.services import rss_feed_service

app = typer.Typer(help="Manage RSS feeds from sources.yaml configuration")
console = Console()


def load_sources_config() -> dict:
    """Load sources configuration from YAML file."""
    config_path = Path(__file__).parent.parent / "config" / "sources.yaml"
    if not config_path.exists():
        console.print(
            f"[red]Error: Configuration file not found at {config_path}[/red]"
        )
        raise typer.Exit(code=1)

    with open(config_path, "r") as f:
        return yaml.safe_load(f)


async def sync_sources_async():
    """Synchronize sources and feeds from YAML to database."""
    config = load_sources_config()
    sources_data = config.get("sources", [])

    if not sources_data:
        console.print("[yellow]No sources found in configuration file[/yellow]")
        return

    async with async_session_maker() as session:
        try:
            stats = {
                "sources_created": 0,
                "sources_found": 0,
                "feeds_created": 0,
                "feeds_found": 0,
            }

            for source_data in sources_data:
                source_name = source_data["name"]
                source_url = source_data["base_url"]

                # Check if source exists
                source = await rss_feed_service.get_source_by_name(session, source_name)

                if not source:
                    # Create new source
                    source = await rss_feed_service.create_source(
                        session, source_name, source_url
                    )
                    stats["sources_created"] += 1
                    console.print(f"[green]✓[/green] Created source: {source_name}")
                else:
                    stats["sources_found"] += 1
                    console.print(
                        f"[blue]ℹ[/blue] Found existing source: {source_name}"
                    )

                # Sync feeds for this source
                for feed_data in source_data.get("feeds", []):
                    feed_url = feed_data["url"]
                    feed_topic = feed_data.get("topic")
                    # Default active unless explicitly set to 0/false
                    raw_is_active = feed_data.get("is_active", 1)
                    is_active = (
                        bool(int(raw_is_active))
                        if isinstance(raw_is_active, (int, str))
                        else bool(raw_is_active)
                    )

                    # Check if feed exists
                    feed = await rss_feed_service.get_feed_by_url(session, feed_url)

                    if not feed:
                        # Create new feed
                        await rss_feed_service.create_feed(
                            session, source.id, feed_url, feed_topic
                        )
                        # Ensure is_active state per config
                        created = await rss_feed_service.get_feed_by_url(
                            session, feed_url
                        )
                        if created is not None:
                            await rss_feed_service.update_feed_fields(
                                session,
                                created.id,
                                topic=feed_topic,
                                is_active=is_active,
                            )
                        stats["feeds_created"] += 1
                        console.print(
                            f"  [green]✓[/green] Created feed: {feed_topic or 'General'} - {feed_url} (active={is_active})"
                        )
                    else:
                        # Update existing feed to match config (but do not delete any others)
                        await rss_feed_service.update_feed_fields(
                            session, feed.id, topic=feed_topic, is_active=is_active
                        )
                        stats["feeds_found"] += 1
                        console.print(
                            f"  [blue]ℹ[/blue] Updated/kept feed: {feed_topic or feed.topic or 'General'} (active={is_active})"
                        )

            await session.commit()

            # Print summary
            console.print("\n[bold]Sync Summary:[/bold]")
            console.print(f"  Sources created: {stats['sources_created']}")
            console.print(f"  Sources found: {stats['sources_found']}")
            console.print(f"  Feeds created: {stats['feeds_created']}")
            console.print(f"  Feeds found: {stats['feeds_found']}")

        except Exception as e:
            await session.rollback()
            console.print(f"[red]Error during sync: {e}[/red]")
            raise typer.Exit(code=1)


async def list_feeds_async():
    """List all feeds from database."""
    async with async_session_maker() as session:
        try:
            feeds = await rss_feed_service.list_all_feeds(session)

            if not feeds:
                console.print("[yellow]No feeds found in database[/yellow]")
                return

            table = Table(
                title="RSS Feeds", show_header=True, header_style="bold magenta"
            )
            table.add_column("Source", style="cyan")
            table.add_column("Topic", style="green")
            table.add_column("Feed URL", style="blue", overflow="fold")
            table.add_column("Active", style="yellow")

            for feed in feeds:
                table.add_row(
                    feed.news_source.name,
                    feed.topic or "General",
                    feed.feed_url,
                    "✓" if feed.is_active else "✗",
                )

            console.print(table)
            console.print(f"\n[bold]Total feeds:[/bold] {len(feeds)}")

        except Exception as e:
            console.print(f"[red]Error listing feeds: {e}[/red]")
            raise typer.Exit(code=1)


async def add_feed_async(source_name: str, feed_url: str, topic: str = None):
    """Add a single feed manually."""
    async with async_session_maker() as session:
        try:
            # Get or create source
            source = await rss_feed_service.get_source_by_name(session, source_name)

            if not source:
                console.print(f"[red]Error: Source '{source_name}' not found[/red]")
                console.print("[yellow]Available sources:[/yellow]")
                config = load_sources_config()
                for s in config.get("sources", []):
                    console.print(f"  - {s['name']}")
                raise typer.Exit(code=1)

            # Check if feed already exists
            existing_feed = await rss_feed_service.get_feed_by_url(session, feed_url)
            if existing_feed:
                console.print(f"[yellow]Feed already exists: {feed_url}[/yellow]")
                raise typer.Exit(code=0)

            # Create feed
            await rss_feed_service.create_feed(session, source.id, feed_url, topic)
            await session.commit()

            console.print(f"[green]✓[/green] Added feed: {topic or 'General'}")
            console.print(f"  Source: {source_name}")
            console.print(f"  URL: {feed_url}")

        except Exception as e:
            await session.rollback()
            console.print(f"[red]Error adding feed: {e}[/red]")
            raise typer.Exit(code=1)


async def remove_feed_async(feed_url: str):
    """Remove a feed by URL."""
    async with async_session_maker() as session:
        try:
            feed = await rss_feed_service.get_feed_by_url(session, feed_url)

            if not feed:
                console.print(f"[yellow]Feed not found: {feed_url}[/yellow]")
                raise typer.Exit(code=0)

            await rss_feed_service.delete_feed(session, feed.id)
            await session.commit()

            console.print(f"[green]✓[/green] Removed feed: {feed_url}")
        except Exception as e:
            await session.rollback()
            console.print(f"[red]Error removing feed: {e}[/red]")
            raise typer.Exit(code=1)


async def set_active_async(feed_url: str, active: bool):
    """Set active status for a feed by URL."""
    async with async_session_maker() as session:
        try:
            feed = await rss_feed_service.get_feed_by_url(session, feed_url)
            if not feed:
                console.print(f"[yellow]Feed not found: {feed_url}[/yellow]")
                raise typer.Exit(code=1)
            await rss_feed_service.update_feed_fields(
                session, feed.id, is_active=active
            )
            await session.commit()
            console.print(f"[green]✓[/green] Set feed active={active}: {feed_url}")
        except Exception as e:
            await session.rollback()
            console.print(f"[red]Error updating feed status: {e}[/red]")
            raise typer.Exit(code=1)


@app.command()
def sync():
    """Sync sources and feeds from sources.yaml to database."""
    console.print("[bold]Syncing feeds from sources.yaml...[/bold]\n")
    asyncio.run(sync_sources_async())


@app.command()
def list():
    """List all feeds from database."""
    asyncio.run(list_feeds_async())


@app.command()
def add(
    source: str = typer.Argument(..., help="Name of the source"),
    url: str = typer.Argument(..., help="RSS feed URL"),
    topic: str = typer.Option(None, "--topic", "-t", help="Feed topic/category"),
):
    """Add a single feed manually."""
    asyncio.run(add_feed_async(source, url, topic))


@app.command()
def remove(
    url: str = typer.Argument(..., help="RSS feed URL to remove"),
):
    """Remove a feed by URL."""
    asyncio.run(remove_feed_async(url))


@app.command("set-active")
def set_active(
    url: str = typer.Argument(..., help="RSS feed URL to update"),
    active: bool = typer.Argument(..., help="true/false to set active status"),
):
    """Set a feed active or inactive by URL."""
    asyncio.run(set_active_async(url, active))


if __name__ == "__main__":
    app()

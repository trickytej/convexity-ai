"""Command-line interface: `digest <command>`."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from .config import get_settings
from .pipeline import (
    acquire_episode,
    discover_show,
    generate_insights,
    ingest_window,
    remap_speakers,
    transcribe_episode,
)
from .registry import load_registry
from .store import get_conn, init_db
from .store import repo
from .store.models import EpisodeStatus

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Turn podcasts into a weekly sector-research digest (Step 1-2: ingest + transcripts).",
)
console = Console()


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, show_path=False, rich_tracebacks=True)],
    )
    # Quiet noisy third-party loggers (full HTTP header/body dumps at DEBUG).
    for name in ("httpx", "httpcore", "anthropic", "assemblyai", "urllib3"):
        logging.getLogger(name).setLevel(logging.WARNING)


def _fmt_dt(dt) -> str:
    return dt.strftime("%Y-%m-%d") if dt else "-"


def _fmt_duration(seconds: int | None) -> str:
    if not seconds:
        return "-"
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


@app.command()
def init(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    """Create data dirs, initialise the database, and sync the show registry."""
    _setup_logging(verbose)
    settings = get_settings()
    settings.ensure_dirs()
    registry = load_registry(settings)
    with get_conn(settings.resolved_db_path) as conn:
        init_db(conn)
        n = repo.sync_shows(conn, registry.shows)
    console.print(
        f"[green]Initialised[/green] db at [cyan]{settings.resolved_db_path}[/cyan] "
        f"with [bold]{n}[/bold] shows ({len(registry.active())} active)."
    )


@app.command()
def shows() -> None:
    """List the configured shows."""
    registry = load_registry()
    table = Table(title="Configured shows", header_style="bold")
    table.add_column("slug")
    table.add_column("tier", justify="center")
    table.add_column("source")
    table.add_column("hosts")
    table.add_column("active", justify="center")
    for s in registry.shows:
        table.add_row(
            s.slug,
            s.tier,
            s.transcript_source,
            ", ".join(s.hosts),
            "[green]yes[/green]" if s.active else "[dim]no[/dim]",
        )
    console.print(table)


@app.command()
def poll(
    show: list[str] = typer.Option(
        None, "--show", "-s", help="Limit to specific show slug(s). Repeatable."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Discover new episodes from the podcast feeds and store their metadata."""
    _setup_logging(verbose)
    settings = get_settings()
    settings.ensure_dirs()
    registry = load_registry(settings)

    targets = registry.active()
    if show:
        wanted = set(show)
        targets = [s for s in targets if s.slug in wanted]
        missing = wanted - {s.slug for s in registry.shows}
        if missing:
            console.print(f"[yellow]Unknown show slug(s): {sorted(missing)}[/yellow]")
    if not targets:
        console.print("[yellow]No matching active shows to poll.[/yellow]")
        raise typer.Exit(code=1)

    table = Table(title="Discovery", header_style="bold")
    table.add_column("show")
    table.add_column("new", justify="right")
    table.add_column("seen", justify="right")
    table.add_column("feed", justify="right")
    table.add_column("result")

    total_new = 0
    with get_conn(settings.resolved_db_path) as conn:
        init_db(conn)
        repo.sync_shows(conn, registry.shows)
        with console.status("[bold]Polling feeds...[/bold]") as status:
            for s in targets:
                status.update(f"[bold]Polling[/bold] {s.slug}...")
                res = discover_show(conn, s, settings)
                total_new += res.new
                if res.error:
                    table.add_row(s.slug, "-", "-", "-", f"[red]{res.error}[/red]")
                else:
                    table.add_row(
                        s.slug,
                        str(res.new),
                        str(res.seen),
                        str(res.total_in_feed),
                        "[green]ok[/green]",
                    )
    console.print(table)
    console.print(f"[bold green]{total_new}[/bold green] new episode(s) discovered.")


@app.command()
def acquire(
    show: list[str] = typer.Option(
        None, "--show", "-s", help="Limit to specific show slug(s). Repeatable."
    ),
    limit: int = typer.Option(5, "--limit", "-n", help="Max episodes to acquire."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Acquire transcripts: Tier A fetches the official transcript (falling back
    to audio); Tier B downloads the audio enclosure for later transcription.

    Processes the most-recent not-yet-acquired episodes first.
    """
    _setup_logging(verbose)
    settings = get_settings()
    settings.ensure_dirs()
    registry = load_registry(settings)
    show_by_slug = {s.slug: s for s in registry.shows}

    table = Table(title="Acquisition", header_style="bold")
    table.add_column("ep", justify="right")
    table.add_column("show")
    table.add_column("action")
    table.add_column("detail")

    wanted = set(show) if show else None
    processed = 0
    with get_conn(settings.resolved_db_path) as conn:
        init_db(conn)
        repo.sync_shows(conn, registry.shows)
        targets = registry.active()
        if wanted:
            targets = [s for s in targets if s.slug in wanted]

        with console.status("[bold]Acquiring...[/bold]") as status_widget:
            for s in targets:
                pending = repo.list_episodes(
                    conn, show_slug=s.slug, status=EpisodeStatus.DISCOVERED, limit=limit
                )
                for ep in pending:
                    status_widget.update(f"[bold]Acquiring[/bold] {s.slug} ep {ep.id}...")
                    res = acquire_episode(conn, ep, show_by_slug[ep.show_slug], settings)
                    processed += 1
                    style = {"official": "green", "audio": "cyan", "failed": "red"}.get(
                        res.action, "white"
                    )
                    table.add_row(
                        str(res.episode_id),
                        s.slug,
                        f"[{style}]{res.action}[/{style}]",
                        res.error or res.detail,
                    )

    console.print(table)
    console.print(f"Processed [bold]{processed}[/bold] episode(s).")


@app.command()
def transcribe(
    show: list[str] = typer.Option(
        None, "--show", "-s", help="Limit to specific show slug(s). Repeatable."
    ),
    limit: int = typer.Option(3, "--limit", "-n", help="Max episodes to transcribe."),
    no_correct: bool = typer.Option(False, "--no-correct", help="Skip the LLM correction pass."),
    no_identify: bool = typer.Option(
        False, "--no-identify", help="Skip LLM speaker-name identification."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Transcribe acquired (audio-downloaded) episodes via AssemblyAI, map speaker
    names, and run the proper-noun correction pass. Requires ASSEMBLYAI_API_KEY
    (and ANTHROPIC_API_KEY for correction/speaker-id).
    """
    _setup_logging(verbose)
    settings = get_settings()
    settings.ensure_dirs()
    registry = load_registry(settings)
    show_by_slug = {s.slug: s for s in registry.shows}

    if not settings.assemblyai_api_key:
        console.print(
            "[red]ASSEMBLYAI_API_KEY is not set.[/red] Add it to .env (see .env.example)."
        )
        raise typer.Exit(code=1)
    if not no_correct and not settings.anthropic_api_key:
        console.print(
            "[yellow]ANTHROPIC_API_KEY not set; correction + speaker-id will be skipped.[/yellow]"
        )

    table = Table(title="Transcription", header_style="bold")
    table.add_column("ep", justify="right")
    table.add_column("show")
    table.add_column("result")
    table.add_column("detail")

    wanted = set(show) if show else None
    processed = 0
    with get_conn(settings.resolved_db_path) as conn:
        init_db(conn)
        repo.sync_shows(conn, registry.shows)
        targets = registry.active()
        if wanted:
            targets = [s for s in targets if s.slug in wanted]
        with console.status("[bold]Transcribing...[/bold]") as widget:
            for s in targets:
                pending = repo.list_episodes(
                    conn, show_slug=s.slug, status=EpisodeStatus.ACQUIRED, limit=limit
                )
                for ep in pending:
                    widget.update(f"[bold]Transcribing[/bold] {s.slug} ep {ep.id}...")
                    res = transcribe_episode(
                        conn,
                        ep,
                        show_by_slug[ep.show_slug],
                        registry.glossary,
                        settings,
                        correct=not no_correct,
                        identify=not no_identify,
                    )
                    processed += 1
                    if res.ok:
                        table.add_row(str(res.episode_id), s.slug, "[green]ok[/green]", res.detail)
                    else:
                        table.add_row(
                            str(res.episode_id), s.slug, "[red]failed[/red]", res.error or ""
                        )
    console.print(table)
    console.print(f"Processed [bold]{processed}[/bold] episode(s).")


@app.command()
def ingest(
    days: int = typer.Option(7, "--days", "-d", help="Ingest episodes published in the last N days."),
    show: list[str] = typer.Option(
        None, "--show", "-s", help="Limit to specific show slug(s). Repeatable."
    ),
    no_correct: bool = typer.Option(False, "--no-correct", help="Skip the LLM correction pass."),
    no_identify: bool = typer.Option(False, "--no-identify", help="Skip speaker-name id."),
    skip_poll: bool = typer.Option(False, "--skip-poll", help="Don't refresh feeds first."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Weekly driver: discover, acquire, and transcribe every episode published in
    the last N days. This is the end-to-end Step 1-2 pipeline for a digest cycle.
    """
    _setup_logging(verbose)
    settings = get_settings()
    settings.ensure_dirs()
    registry = load_registry(settings)

    if not settings.assemblyai_api_key:
        console.print(
            "[red]ASSEMBLYAI_API_KEY is not set.[/red] Add it to .env (see .env.example)."
        )
        raise typer.Exit(code=1)
    if not no_correct and not settings.anthropic_api_key:
        console.print(
            "[yellow]ANTHROPIC_API_KEY not set; correction + speaker-id will be skipped.[/yellow]"
        )

    table = Table(title=f"Ingest (last {days} days)", header_style="bold")
    table.add_column("ep", justify="right")
    table.add_column("show")
    table.add_column("stage")
    table.add_column("detail")

    with get_conn(settings.resolved_db_path) as conn:
        init_db(conn)
        repo.sync_shows(conn, registry.shows)
        with console.status("[bold]Ingesting...[/bold]") as widget:
            outcomes = ingest_window(
                conn,
                registry,
                settings,
                days=days,
                only=set(show) if show else None,
                correct=not no_correct,
                identify=not no_identify,
                skip_poll=skip_poll,
                progress=lambda msg: widget.update(f"[bold]{msg}[/bold]"),
            )

    counts = {"official": 0, "transcribed": 0, "failed": 0}
    for o in outcomes:
        counts[o.stage] = counts.get(o.stage, 0) + 1
        style = {"official": "green", "transcribed": "cyan", "failed": "red"}.get(o.stage, "white")
        title = (o.title[:46] + "...") if len(o.title) > 49 else o.title
        table.add_row(
            str(o.episode_id), o.show_slug, f"[{style}]{o.stage}[/{style}]", o.error or o.detail
        )
        table.add_row("", "", "", f"[dim]{title}[/dim]")
    console.print(table)
    console.print(
        f"Done: [cyan]{counts['transcribed']}[/cyan] transcribed, "
        f"[green]{counts['official']}[/green] official, [red]{counts['failed']}[/red] failed."
    )


@app.command(name="remap-speakers")
def remap_speakers_cmd(
    show: list[str] = typer.Option(None, "--show", "-s", help="Limit to show slug(s)."),
    all_episodes: bool = typer.Option(
        False, "--all", help="Re-map all ASR transcripts, not just placeholder ones."
    ),
    limit: int = typer.Option(None, "--limit", "-n"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Re-run speaker-name identification on stored ASR transcripts (reuses saved
    diarization labels; no re-transcription). Fixes episodes left with "Speaker A/B".
    """
    _setup_logging(verbose)
    settings = get_settings()
    registry = load_registry(settings)
    if not settings.anthropic_api_key:
        console.print("[red]ANTHROPIC_API_KEY is not set.[/red]")
        raise typer.Exit(code=1)

    table = Table(title="Speaker re-map", header_style="bold")
    table.add_column("ep", justify="right")
    table.add_column("show")
    table.add_column("speakers")
    with get_conn(settings.resolved_db_path) as conn:
        init_db(conn)
        repo.sync_shows(conn, registry.shows)
        with console.status("[bold]Re-mapping speakers...[/bold]") as widget:
            outcomes = remap_speakers(
                conn,
                registry,
                settings,
                only=set(show) if show else None,
                only_placeholder=not all_episodes,
                limit=limit,
                progress=lambda msg: widget.update(f"[bold]{msg}[/bold]"),
            )
    for o in outcomes:
        table.add_row(str(o.episode_id), o.show_slug, ", ".join(o.speakers))
    console.print(table)
    console.print(f"Re-mapped [bold]{len(outcomes)}[/bold] transcript(s).")


@app.command()
def insights(
    show: list[str] = typer.Option(None, "--show", "-s", help="Limit to show slug(s)."),
    days: int = typer.Option(None, "--days", "-d", help="Only episodes published in the last N days."),
    limit: int = typer.Option(None, "--limit", "-n", help="Max episodes to process."),
    force: bool = typer.Option(False, "--force", help="Re-extract even if nuggets exist (drops triage)."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Step 3: extract investment nuggets from transcribed episodes. Requires
    ANTHROPIC_API_KEY. Skips episodes already processed unless --force.
    """
    _setup_logging(verbose)
    settings = get_settings()
    settings.ensure_dirs()
    registry = load_registry(settings)
    show_by_slug = {s.slug: s for s in registry.shows}

    if not settings.anthropic_api_key:
        console.print("[red]ANTHROPIC_API_KEY is not set.[/red] Add it to .env.")
        raise typer.Exit(code=1)

    since = datetime.now(timezone.utc) - timedelta(days=days) if days else None
    wanted = set(show) if show else None

    table = Table(title="Insights (nuggets)", header_style="bold")
    table.add_column("ep", justify="right")
    table.add_column("show")
    table.add_column("nuggets", justify="right")
    table.add_column("result")

    total = 0
    with get_conn(settings.resolved_db_path) as conn:
        init_db(conn)
        repo.sync_shows(conn, registry.shows)
        episodes_list = repo.list_episodes(
            conn, status=EpisodeStatus.TRANSCRIBED, published_since=since
        )
        if wanted:
            episodes_list = [e for e in episodes_list if e.show_slug in wanted]
        if limit:
            episodes_list = episodes_list[:limit]

        with console.status("[bold]Extracting nuggets...[/bold]") as widget:
            for ep in episodes_list:
                widget.update(f"[bold]Insights[/bold] {ep.show_slug} ep {ep.id}...")
                res = generate_insights(conn, ep, show_by_slug[ep.show_slug], settings, force=force)
                if res.ok and not res.skipped:
                    total += res.count
                style = "dim" if res.skipped else ("green" if res.ok else "red")
                table.add_row(
                    str(ep.id), ep.show_slug, str(res.count), f"[{style}]{res.error or res.detail}[/{style}]"
                )
    console.print(table)
    console.print(f"Extracted [bold green]{total}[/bold green] nugget(s).")


@app.command()
def nuggets(
    episode: int = typer.Option(None, "--episode", "-e", help="Filter by episode id."),
    show: str = typer.Option(None, "--show", "-s", help="Filter by show slug."),
    type_: str = typer.Option(None, "--type", "-t", help="Filter by nugget type."),
    min_signal: float = typer.Option(0.0, "--min-signal", help="Minimum signal score (0-1)."),
    limit: int = typer.Option(20, "--limit", "-n"),
) -> None:
    """List extracted nuggets (highest signal first)."""
    settings = get_settings()
    with get_conn(settings.resolved_db_path) as conn:
        ep_filter: set[int] | None = None
        if show:
            ep_filter = {e.id for e in repo.list_episodes(conn, show_slug=show) if e.id is not None}
        rows = repo.list_nuggets(
            conn,
            episode_id=episode,
            nugget_type=type_,
            min_signal=min_signal,
            limit=None if ep_filter is not None else limit,
        )
        if ep_filter is not None:
            rows = [n for n in rows if n.episode_id in ep_filter][:limit]

    table = Table(title=f"Nuggets (showing {len(rows)})", header_style="bold")
    table.add_column("ep", justify="right")
    table.add_column("score", justify="right")
    table.add_column("type")
    table.add_column("speaker")
    table.add_column("claim")
    for n in rows:
        mark = "" if n.quote_verified else " [dim](unverified)[/dim]"
        claim = (n.claim[:88] + "…") if len(n.claim) > 90 else n.claim
        table.add_row(
            str(n.episode_id),
            f"{n.signal_score:.2f}",
            n.type,
            n.speaker_name or "-",
            claim + mark,
        )
    console.print(table)


@app.command()
def episodes(
    show: str = typer.Option(None, "--show", "-s", help="Filter by show slug."),
    status: str = typer.Option(None, "--status", help="Filter by status."),
    limit: int = typer.Option(20, "--limit", "-n"),
) -> None:
    """List stored episodes (most recent first)."""
    settings = get_settings()
    status_enum = EpisodeStatus(status) if status else None
    with get_conn(settings.resolved_db_path) as conn:
        rows = repo.list_episodes(conn, show_slug=show, status=status_enum, limit=limit)

    table = Table(title=f"Episodes (showing {len(rows)})", header_style="bold")
    table.add_column("id", justify="right")
    table.add_column("show")
    table.add_column("date")
    table.add_column("dur", justify="right")
    table.add_column("status")
    table.add_column("title")
    for ep in rows:
        table.add_row(
            str(ep.id),
            ep.show_slug,
            _fmt_dt(ep.published_at),
            _fmt_duration(ep.duration_seconds),
            ep.status.value,
            (ep.title[:70] + "...") if len(ep.title) > 73 else ep.title,
        )
    console.print(table)


@app.command()
def status() -> None:
    """Show per-show episode counts by pipeline stage."""
    settings = get_settings()
    with get_conn(settings.resolved_db_path) as conn:
        rows = repo.status_matrix(conn)

    table = Table(title="Pipeline status", header_style="bold")
    table.add_column("show")
    table.add_column("tier", justify="center")
    table.add_column("total", justify="right")
    table.add_column("discovered", justify="right")
    table.add_column("acquired", justify="right")
    table.add_column("transcribed", justify="right")
    table.add_column("failed", justify="right")
    for r in rows:
        name = r["slug"] if r["active"] else f"[dim]{r['slug']} (off)[/dim]"
        table.add_row(
            name,
            r["tier"],
            str(r["total"] or 0),
            str(r["discovered"] or 0),
            str(r["acquired"] or 0),
            str(r["transcribed"] or 0),
            str(r["failed"] or 0),
        )
    console.print(table)


@app.command()
def reclassify(
    all_nuggets: bool = typer.Option(
        False, "--all", help="Reclassify every nugget, not just unclassified ones."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Assign each nugget a controlled primary_sector (AI is treated as cross-cutting,
    not a catch-all bucket). Cheap batched LLM pass; safe to re-run.
    """
    _setup_logging(verbose)
    settings = get_settings()
    if not settings.anthropic_api_key:
        console.print("[red]ANTHROPIC_API_KEY is not set.[/red]")
        raise typer.Exit(code=1)
    from .sectors import reclassify as run_reclassify

    with get_conn(settings.resolved_db_path) as conn:
        init_db(conn)
        with console.status("[bold]Classifying sectors...[/bold]") as widget:
            n = run_reclassify(
                conn,
                settings,
                only_missing=not all_nuggets,
                progress=lambda done, total: widget.update(
                    f"[bold]Classifying {done}/{total}...[/bold]"
                ),
            )
    console.print(f"Set primary_sector on [bold green]{n}[/bold green] nugget(s).")


@app.command()
def newsletter(
    from_date: str = typer.Option(
        None, "--from", help="Start date YYYY-MM-DD (default: 7 days ago)."
    ),
    to_date: str = typer.Option(
        None, "--to", help="End date YYYY-MM-DD (default: today)."
    ),
    days: int = typer.Option(
        None, "--days", "-d", help="Shorthand: last N days (overrides --from/--to)."
    ),
    output: str = typer.Option(
        None, "--output", "-o", help="Write rendered markdown to this path. Defaults to stdout."
    ),
) -> None:
    """Render a newsletter from kept insights in a date window.

    Outputs markdown (stdout or --output path).  Requires curator decisions to
    have been set via the Review tab or PATCH /api/nuggets/{id}/curation first.
    """
    from datetime import date, timedelta

    from .api.routers.newsletter import (
        _build_stock_readthrough,
        _nugget_out,
        _render_markdown,
    )

    today = date.today()
    if days is not None:
        resolved_from = (today - timedelta(days=days)).isoformat()
        resolved_to = today.isoformat()
    else:
        resolved_from = from_date or (today - timedelta(days=7)).isoformat()
        resolved_to = to_date or today.isoformat()

    from_iso = f"{resolved_from}T00:00:00+00:00"
    to_iso = f"{resolved_to}T23:59:59+00:00"

    settings = get_settings()
    with get_conn(settings.resolved_db_path) as conn:
        init_db(conn)
        rows = repo.list_kept_nuggets_for_newsletter(conn, from_iso, to_iso)

    nuggets_out = [_nugget_out(r) for r in rows]
    lead = [n for n in nuggets_out if n.curator_rank == 1]
    good_to_know = [n for n in nuggets_out if n.curator_rank != 1]
    stocks = _build_stock_readthrough(rows)
    episode_count = len({r["episode_id"] for r in rows})

    md = _render_markdown(
        resolved_from, resolved_to, lead, good_to_know, stocks, episode_count, len(rows)
    )

    if output:
        from pathlib import Path
        Path(output).write_text(md, encoding="utf-8")
        console.print(f"[green]Wrote newsletter to[/green] [cyan]{output}[/cyan]")
        console.print(
            f"  {episode_count} episode(s) · [bold]{len(rows)}[/bold] kept · "
            f"{len(lead)} lead · {len(good_to_know)} good-to-know"
        )
    else:
        console.print(md)


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8000, "--port", help="API port (avoid 8080)."),
    reload: bool = typer.Option(False, "--reload", help="Auto-reload on code changes (dev)."),
) -> None:
    """Run the web API (FastAPI) that backs the frontend."""
    import uvicorn

    console.print(f"[green]Serving API[/green] at http://{host}:{port}  (docs at /docs)")
    uvicorn.run("digest.api.app:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()

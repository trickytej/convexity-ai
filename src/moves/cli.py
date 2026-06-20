"""`moves` command-line interface."""

from __future__ import annotations

from datetime import date, timedelta

import typer
from polygon.websocket.models import Feed
from rich.console import Console
from rich.table import Table

from moves import __version__
from moves.config import get_settings, load_watchlist
from moves.engine import build_basket, detect_moves, detect_spikes, volatility_threshold
from moves.ingest import backfill
from moves.insights import attribute_move, investigate_move
from moves.models import Move, Rebalance, Weighting
from moves.providers import PolygonClient, stream_aggregates
from moves.store import bar_counts, connect, get_bars, init_db
from moves.synthetic import gbm_series

app = typer.Typer(add_completion=False, help="Market move-intelligence toolkit.")
console = Console()


def _moves_table(title: str, moves: list[Move]) -> Table:
    table = Table(title=title, header_style="bold")
    table.add_column("#", justify="right")
    table.add_column("Dir")
    table.add_column("Start")
    table.add_column("End")
    table.add_column("From", justify="right")
    table.add_column("To", justify="right")
    table.add_column("Move", justify="right")
    table.add_column("Bars", justify="right")
    table.add_column("MaxAdv", justify="right")
    table.add_column("Conf")
    for i, m in enumerate(moves, 1):
        color = "green" if m.direction.value == "up" else "red"
        start = m.start_ts.date().isoformat() if m.start_ts else str(m.start_index)
        end = m.end_ts.date().isoformat() if m.end_ts else str(m.end_index)
        table.add_row(
            str(i),
            f"[{color}]{m.direction.value}[/{color}]",
            start,
            end,
            f"{m.start_price:.2f}",
            f"{m.end_price:.2f}",
            f"[{color}]{m.pct_change * 100:+.1f}%[/{color}]",
            str(m.n_bars),
            f"{m.max_adverse_pct * 100:.1f}%",
            "Y" if m.confirmed else "open",
        )
    return table


@app.command()
def version() -> None:
    """Print the package version."""
    console.print(f"market-moves {__version__}")


@app.command()
def watchlist() -> None:
    """Show the configured instrument watchlist."""
    instruments = load_watchlist()
    table = Table(title=f"Watchlist ({len(instruments)} instruments)", header_style="bold")
    table.add_column("Ticker")
    table.add_column("Name")
    table.add_column("Group")
    for inst in instruments:
        table.add_row(inst.ticker, inst.name, inst.group)
    console.print(table)


@app.command()
def demo(
    days: int = typer.Option(252, help="Number of business days to simulate."),
    threshold: float = typer.Option(0.05, help="Move reversal threshold (fraction)."),
    seed: int = typer.Option(7, help="RNG seed for reproducibility."),
    vol_normalize: bool = typer.Option(
        False, help="Use a volatility-scaled per-bar threshold instead of a constant."
    ),
) -> None:
    """Run move detection + basket construction on synthetic data (no API key)."""
    series = gbm_series(days=days, seed=seed, jumps={50: -0.14, 120: 0.18, 200: -0.09})
    prices = series.to_numpy()
    timestamps = list(series.index.to_pydatetime())

    thr = volatility_threshold(prices) if vol_normalize else threshold
    moves = detect_moves(prices, timestamps, threshold=thr, symbol="DEMO")
    console.print(_moves_table(f"DEMO moves (threshold {threshold:.0%})", moves))

    basket = build_basket(
        {
            "A": gbm_series(days=days, seed=seed, jumps={50: -0.14}),
            "B": gbm_series(days=days, seed=seed + 1, mu=0.12),
            "C": gbm_series(days=days, seed=seed + 2, sigma=0.35, jumps={120: 0.2}),
        },
        weighting=Weighting.EQUAL,
        rebalance=Rebalance.MONTHLY,
    )
    b_moves = detect_moves(
        basket.index.to_numpy(),
        list(basket.index.index.to_pydatetime()),
        threshold=threshold,
        symbol="BASKET",
    )
    console.print(
        f"\nEqual-weight basket (A,B,C), start 100.00 -> end "
        f"{basket.index.iloc[-1]:.2f}; detected {len(b_moves)} moves."
    )
    console.print(_moves_table("BASKET moves", b_moves))


@app.command()
def init() -> None:
    """Create the local data directory and DuckDB schema."""
    con = connect()
    init_db(con)
    con.close()
    console.print(f"Initialized store at {get_settings().duckdb_path}")


@app.command()
def ingest(
    symbol: str = typer.Option(None, "-s", "--symbol", help="One ticker; default = watchlist."),
    timeframe: str = typer.Option("day", help="Bar timeframe (day, hour, minute, 5min, ...)."),
    years: float = typer.Option(5.0, help="Years of history (ignored when --start is given)."),
    start: str = typer.Option(None, help="ISO start date YYYY-MM-DD."),
    end: str = typer.Option(None, help="ISO end date; default today."),
    corporate_actions: bool = typer.Option(True, help="Also fetch splits + dividends."),
    news: bool = typer.Option(False, help="Also fetch recent ticker news."),
) -> None:
    """Backfill bars from Polygon into the store (idempotent)."""
    instruments = load_watchlist()
    symbols = [symbol.upper()] if symbol else [i.ticker for i in instruments]
    end = end or date.today().isoformat()
    if not start:
        start = (date.today() - timedelta(days=int(365 * years))).isoformat()

    con = connect()
    init_db(con)
    client = PolygonClient()
    console.print(f"Backfilling {len(symbols)} symbol(s), {timeframe} bars, {start}..{end}")

    def progress(sym: str, n: int) -> None:
        console.print(f"  {sym}: {n} bars")

    written = backfill(
        con,
        client,
        symbols,
        timeframe,
        start,
        end,
        corporate_actions=corporate_actions,
        news=news,
        progress=progress,
    )
    con.close()
    console.print(f"Done. {sum(written.values())} bars across {len(written)} symbol(s).")


@app.command()
def status() -> None:
    """Show per-symbol/timeframe coverage in the store."""
    con = connect()
    init_db(con)
    df = bar_counts(con)
    con.close()
    if df.empty:
        console.print("No bars stored yet. Run `moves ingest`.")
        return
    table = Table(title="Store coverage", header_style="bold")
    for col in ("Symbol", "Timeframe", "Bars", "First", "Last"):
        table.add_column(col)
    for _, r in df.iterrows():
        table.add_row(
            r["symbol"],
            r["timeframe"],
            f"{int(r['n_bars']):,}",
            str(r["first_ts"])[:10],
            str(r["last_ts"])[:19],
        )
    console.print(table)


@app.command()
def bars(
    symbol: str = typer.Option(..., "-s", "--symbol"),
    timeframe: str = typer.Option("day"),
    n: int = typer.Option(10, "-n", "--limit", help="Show the last N bars."),
) -> None:
    """Print the most recent stored bars for a symbol."""
    con = connect()
    init_db(con)
    df = get_bars(con, symbol.upper(), timeframe)
    con.close()
    if df.empty:
        console.print(f"No {timeframe} bars for {symbol.upper()}. Run `moves ingest -s {symbol}`.")
        return
    tail = df.tail(n)
    table = Table(
        title=f"{symbol.upper()} {timeframe} (last {len(tail)} of {len(df)})", header_style="bold"
    )
    for col in ("Date", "Open", "High", "Low", "Close", "Volume"):
        table.add_column(col, justify="right")
    for _, r in tail.iterrows():
        table.add_row(
            str(r["ts"])[:19],
            f"{r['open']:.2f}",
            f"{r['high']:.2f}",
            f"{r['low']:.2f}",
            f"{r['close']:.2f}",
            f"{r['volume']:,.0f}",
        )
    console.print(table)


@app.command()
def detect(
    symbol: str = typer.Option(..., "-s", "--symbol"),
    timeframe: str = typer.Option("day"),
    threshold: float = typer.Option(0.05, help="Reversal threshold (fraction)."),
    min_move: float = typer.Option(None, help="Only surface moves >= this magnitude."),
    vol_normalize: bool = typer.Option(False, help="Use a volatility-scaled threshold."),
) -> None:
    """Detect significant moves on stored bars for a symbol."""
    con = connect()
    init_db(con)
    df = get_bars(con, symbol.upper(), timeframe)
    con.close()
    if df.empty:
        console.print(f"No {timeframe} bars for {symbol.upper()}. Run `moves ingest -s {symbol}`.")
        return
    prices = df["close"].to_numpy()
    timestamps = df["ts"].dt.to_pydatetime().tolist()
    thr = volatility_threshold(prices) if vol_normalize else threshold
    moves = detect_moves(
        prices, timestamps, threshold=thr, min_move=min_move, symbol=symbol.upper()
    )
    console.print(
        _moves_table(f"{symbol.upper()} {timeframe} moves (>= {threshold:.0%})", moves)
    )


@app.command()
def explain(
    symbol: str = typer.Option(..., "-s", "--symbol"),
    timeframe: str = typer.Option("day"),
    threshold: float = typer.Option(0.08, help="Reversal threshold (fraction)."),
    index: int = typer.Option(-1, help="Which detected move to explain (-1 = most recent)."),
) -> None:
    """Generate a grounded AI attribution for one detected move (uses Anthropic)."""
    con = connect()
    init_db(con)
    df = get_bars(con, symbol.upper(), timeframe)
    if df.empty:
        console.print(f"No {timeframe} bars for {symbol.upper()}. Run `moves ingest -s {symbol}`.")
        con.close()
        return
    prices = df["close"].to_numpy()
    times = df["ts"].astype("datetime64[s]").astype("int64").tolist()
    moves = detect_moves(prices, threshold=threshold, symbol=symbol.upper())
    if not moves:
        console.print("No moves at this threshold.")
        con.close()
        return
    m = moves[index]
    console.print(
        f"[bold]{symbol.upper()} {m.direction.value} {m.pct_change * 100:+.1f}%[/bold] "
        f"({df['ts'].iloc[m.start_index].date()} -> "
        f"{df['ts'].iloc[m.end_index].date()}) — attributing…"
    )
    payload = attribute_move(
        con,
        symbol=symbol.upper(),
        timeframe=timeframe,
        start_time=times[m.start_index],
        end_time=times[m.end_index],
        direction=m.direction.value,
        pct_change=m.pct_change,
    )
    con.close()
    sc = payload["sources_considered"]
    console.print(
        f"\n[bold]{payload.get('horizon', '?')}-term · scope: {payload.get('scope') or '?'} · "
        f"confidence: {payload['confidence']}[/bold]"
    )
    console.print(payload["summary"] or "(no clear catalyst)")
    console.print(
        f"[dim]considered {sc['news']} news, {sc['podcast']} podcast, "
        f"{sc['corporate_action']} corp-action, {sc['peers']} peers[/dim]\n"
    )
    for e in payload["evidence"]:
        url = f"  {e['url']}" if e.get("url") else ""
        console.print(f"  - ({e['kind']}) {e['point']}{url}")


@app.command()
def investigate(
    symbol: str = typer.Option(..., "-s", "--symbol"),
    timeframe: str = typer.Option("hour"),
    threshold: float = typer.Option(0.04, help="Spike threshold (fraction)."),
    spike_minutes: int = typer.Option(240, help="Max spike duration (minutes)."),
    index: int = typer.Option(0, help="Which scanned spike to investigate (0 = biggest)."),
) -> None:
    """Agentic Opus deep-dive: investigate a move's cause with tool use."""
    con = connect()
    init_db(con)
    df = get_bars(con, symbol.upper(), timeframe)
    if df.empty:
        console.print(f"No {timeframe} bars for {symbol.upper()}. Run `moves ingest -s {symbol}`.")
        con.close()
        return
    prices = df["close"].to_numpy()
    times = df["ts"].astype("datetime64[s]").astype("int64").tolist()
    tf_min = {"minute": 1, "5min": 5, "15min": 15, "hour": 60, "day": 390, "week": 1950}
    max_bars = max(1, round(spike_minutes / tf_min.get(timeframe, 15)))
    spikes = detect_spikes(prices, threshold=threshold, max_bars=max_bars, symbol=symbol.upper())
    if not spikes:
        console.print("No spikes at this threshold.")
        con.close()
        return
    spikes.sort(key=lambda m: abs(m.pct_change), reverse=True)
    m = spikes[index]
    console.print(
        f"Investigating {symbol.upper()} {m.direction.value} {m.pct_change * 100:+.1f}% "
        f"({df['ts'].iloc[m.start_index]} -> "
        f"{df['ts'].iloc[m.end_index]}) — running Opus agent…"
    )
    payload = investigate_move(
        con,
        symbol=symbol.upper(),
        timeframe=timeframe,
        start_time=times[m.start_index],
        end_time=times[m.end_index],
        direction=m.direction.value,
        pct_change=m.pct_change,
    )
    con.close()
    console.print(f"\n[dim]tools: {' | '.join(payload['trace'])}[/dim]")
    console.print(
        f"\n[bold]{payload['horizon']}-term · scope {payload['scope'] or '?'} · "
        f"confidence {payload['confidence']}[/bold]"
    )
    console.print(payload["summary"] or "(no conclusion)")
    console.print("\n[bold]Evidence:[/bold]")
    for e in payload["evidence"]:
        url = f"  {e['url']}" if e.get("url") else ""
        timing = f"  ({e['timing']})" if e.get("timing") else ""
        console.print(f"  - ({e['kind']}) {e['point']}{timing}{url}")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind host."),
    port: int = typer.Option(8001, help="Bind port."),
    reload: bool = typer.Option(False, help="Auto-reload on code changes (dev)."),
) -> None:
    """Run the FastAPI server (API + docs at /docs)."""
    import uvicorn

    uvicorn.run("moves.api.app:app", host=host, port=port, reload=reload)


@app.command()
def stream(
    symbols: str = typer.Argument(..., help="Comma-separated tickers, e.g. NVDA,AMD"),
    seconds: float = typer.Option(15.0, help="How long to stream before closing."),
    delayed: bool = typer.Option(False, help="Use the delayed feed instead of real-time."),
) -> None:
    """Stream live minute aggregates over the Polygon WebSocket (markets must be open)."""
    tickers = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    feed = Feed.Delayed if delayed else Feed.RealTime
    received = {"n": 0}

    def on_bar(message: object) -> None:
        received["n"] += 1
        console.print(message)

    console.print(
        f"Streaming {tickers} (feed={feed.name}) for {seconds:.0f}s. "
        "Live aggregates only flow during market hours."
    )
    stream_aggregates(tickers, on_bar, feed=feed, max_seconds=seconds)
    console.print(f"Stream closed. Received {received['n']} message(s).")


if __name__ == "__main__":
    app()

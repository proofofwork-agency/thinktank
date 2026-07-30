from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from rapana.logging import get_logger

log = get_logger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS candles (
    symbol    TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    ts        INTEGER NOT NULL,
    open      REAL NOT NULL,
    high      REAL NOT NULL,
    low       REAL NOT NULL,
    close     REAL NOT NULL,
    volume    REAL NOT NULL,
    PRIMARY KEY (symbol, timeframe, ts)
);

CREATE INDEX IF NOT EXISTS idx_candles_symbol_tf_ts
    ON candles(symbol, timeframe, ts);

CREATE TABLE IF NOT EXISTS funding (
    symbol       TEXT NOT NULL,    -- perp symbol, e.g. BTC/USDT:USDT
    ts           INTEGER NOT NULL, -- funding settlement time (epoch ms)
    funding_rate REAL NOT NULL,    -- signed per-interval rate (longs pay shorts if > 0)
    PRIMARY KEY (symbol, ts)
);

CREATE INDEX IF NOT EXISTS idx_funding_symbol_ts
    ON funding(symbol, ts);

CREATE TABLE IF NOT EXISTS macro_series (
    name  TEXT NOT NULL,    -- series id, e.g. 'fear_greed'
    ts    INTEGER NOT NULL, -- epoch ms (day-start for daily series)
    value REAL NOT NULL,
    PRIMARY KEY (name, ts)
);

CREATE INDEX IF NOT EXISTS idx_macro_name_ts
    ON macro_series(name, ts);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


class TimeSeriesStore:
    """SQLite-backed OHLCV store for Phase 0.

    Upgrade path: swap for TimescaleDB / QuestDB / ClickHouse in Phase 4 once
    throughput demands it. The public surface (upsert_candles, fetch_candles)
    is intended to stay stable.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript(_SCHEMA)

    def upsert_candles(
        self, symbol: str, timeframe: str, candles: list[list[int | float]]
    ) -> int:
        """Insert/replace OHLCV rows. Returns number of rows written."""
        rows = [
            (symbol.upper(), timeframe, int(c[0]), float(c[1]), float(c[2]),
             float(c[3]), float(c[4]), float(c[5]))
            for c in candles
        ]
        with self._conn() as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO candles
                   (symbol, timeframe, ts, open, high, low, close, volume)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )
        return len(rows)

    def fetch_candles(
        self, symbol: str, timeframe: str, limit: int = 500
    ) -> list[dict[str, Any]]:
        with self._conn() as conn:
            cur = conn.execute(
                """SELECT ts, open, high, low, close, volume
                   FROM candles
                   WHERE symbol = ? AND timeframe = ?
                   ORDER BY ts DESC LIMIT ?""",
                (symbol.upper(), timeframe, limit),
            )
            rows = [dict(r) for r in cur.fetchall()]
        rows.reverse()  # ascending time order
        return rows

    def fetch_candles_range(
        self,
        symbol: str,
        timeframe: str,
        since: int | None = None,
        until: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return ALL stored candles in [since, until] ascending (no LIMIT).

        Bounds are epoch milliseconds; ``None`` means unbounded on that side.
        Used by backtest/validation so repeated runs read history from the store
        instead of re-hitting the exchange.
        """
        with self._conn() as conn:
            cur = conn.execute(
                """SELECT ts, open, high, low, close, volume
                   FROM candles
                   WHERE symbol = ? AND timeframe = ?
                     AND (? IS NULL OR ts >= ?)
                     AND (? IS NULL OR ts <= ?)
                   ORDER BY ts ASC""",
                (symbol.upper(), timeframe, since, since, until, until),
            )
            return [dict(r) for r in cur.fetchall()]

    def symbols(self, timeframe: str) -> list[str]:
        """Distinct symbols stored for a timeframe (the validation candidate set)."""
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT DISTINCT symbol FROM candles WHERE timeframe = ? ORDER BY symbol",
                (timeframe,),
            )
            return [r["symbol"] for r in cur.fetchall()]

    def last_timestamp(self, symbol: str, timeframe: str) -> int | None:
        with self._conn() as conn:
            cur = conn.execute(
                """SELECT MAX(ts) AS ts FROM candles
                   WHERE symbol = ? AND timeframe = ?""",
                (symbol.upper(), timeframe),
            )
            row = cur.fetchone()
            return int(row["ts"]) if row and row["ts"] is not None else None

    # ---- funding-rate history (carry track, C1) -------------------------
    def upsert_funding(
        self, symbol: str, rows: list[dict[str, Any]]
    ) -> int:
        """Insert/replace funding rows. Each row is {ts, funding_rate}.

        ``symbol`` is the perp symbol (e.g. ``BTC/USDT:USDT``). Idempotent via
        INSERT OR REPLACE so resumable ingestion never duplicates. Returns the
        number of rows written.
        """
        out = [
            (symbol.upper(), int(r["ts"]), float(r["funding_rate"]))
            for r in rows
        ]
        with self._conn() as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO funding (symbol, ts, funding_rate)
                   VALUES (?, ?, ?)""",
                out,
            )
        return len(out)

    def fetch_funding_range(
        self,
        symbol: str,
        since: int | None = None,
        until: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return ALL stored funding rows in [since, until] ascending (no LIMIT).

        Bounds are epoch milliseconds; ``None`` means unbounded on that side.
        Mirrors ``fetch_candles_range`` so the carry backtest reads from the
        store instead of re-hitting the exchange.
        """
        with self._conn() as conn:
            cur = conn.execute(
                """SELECT ts, funding_rate
                   FROM funding
                   WHERE symbol = ?
                     AND (? IS NULL OR ts >= ?)
                     AND (? IS NULL OR ts <= ?)
                   ORDER BY ts ASC""",
                (symbol.upper(), since, since, until, until),
            )
            return [dict(r) for r in cur.fetchall()]

    def funding_symbols(self) -> list[str]:
        """Distinct perp symbols with stored funding history."""
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT DISTINCT symbol FROM funding ORDER BY symbol"
            )
            return [r["symbol"] for r in cur.fetchall()]

    def last_funding_timestamp(self, symbol: str) -> int | None:
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT MAX(ts) AS ts FROM funding WHERE symbol = ?",
                (symbol.upper(),),
            )
            row = cur.fetchone()
            return int(row["ts"]) if row and row["ts"] is not None else None

    def set_meta(self, key: str, value: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                (key, value),
            )

    def get_meta(self, key: str) -> str | None:
        with self._conn() as conn:
            cur = conn.execute("SELECT value FROM meta WHERE key = ?", (key,))
            row = cur.fetchone()
            return row["value"] if row else None

    # ---- macro series (market-wide signals: Fear&Greed, etc.) -----------
    def upsert_macro_series(self, name: str, rows: list[dict[str, Any]]) -> int:
        """Insert/replace rows for a market-wide daily series. Each row is
        ``{ts, value}`` (ts in epoch ms). Idempotent via INSERT OR REPLACE."""
        out = [(name, int(r["ts"]), float(r["value"])) for r in rows]
        with self._conn() as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO macro_series (name, ts, value)
                   VALUES (?, ?, ?)""",
                out,
            )
        return len(out)

    def fetch_macro_series(
        self,
        name: str,
        since: int | None = None,
        until: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return ALL stored rows for a macro series in [since, until] ascending."""
        with self._conn() as conn:
            cur = conn.execute(
                """SELECT ts, value FROM macro_series
                   WHERE name = ?
                     AND (? IS NULL OR ts >= ?)
                     AND (? IS NULL OR ts <= ?)
                   ORDER BY ts ASC""",
                (name, since, since, until, until),
            )
            return [dict(r) for r in cur.fetchall()]

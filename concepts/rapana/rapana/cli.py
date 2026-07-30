from __future__ import annotations

import argparse
import sys
from decimal import Decimal

from rapana.agents import ComplianceAuditor
from rapana.backtest.engine import BacktestConfig, BacktestEngine
from rapana.config import get_settings
from rapana.data.ingest import MarketDataIngester
from rapana.data.store import TimeSeriesStore
from rapana.fleet import (
    Autopilot,
    AutopilotPolicy,
    Fleet,
    FleetConfig,
    FleetRunner,
    PaperExecutor,
    PerformanceTracker,
    ReplayProvider,
    StagedCapital,
    StoreDataProvider,
)
from rapana.fleet.execution import ExecutionTrader
from rapana.fleet.maker_fill import PaperMakerFillModel
from rapana.fleet.runner import format_paper_maker_eval_report, summarize_paper_maker_eval
from rapana.journal.ledger import DecisionLedger
from rapana.logging import configure_logging, get_logger
from rapana.mexc.client import MexcClient
from rapana.notify import NullNotifier, build_notifier
from rapana.risk.guardrails import (
    CircuitBreaker,
    KillSwitch,
    PreTradeChecker,
    RiskPolicy,
    TradeProposal,
)
from rapana.risk.live_safety import preflight
from rapana.strategies import Breakout, MeanReversion, TrendFollowing

log = get_logger(__name__)

_STRATEGIES = {"trend": TrendFollowing, "meanrev": MeanReversion, "breakout": Breakout}


def _cmd_status(args: argparse.Namespace) -> int:
    settings = get_settings()
    configure_logging()
    client = MexcClient(settings=settings)
    print(f"env         : {settings.env} ({'LIVE' if settings.is_live else 'PAPER'})")
    print(f"symbols     : {', '.join(settings.watch_symbols)}")
    print(f"kill switch : {'TRIPPED' if KillSwitch(settings=settings).is_tripped() else 'clear'}")
    ok = client.ping()
    print(f"mexc ping   : {'ok' if ok else 'FAILED'}")
    if ok:
        try:
            bal = client.fetch_balance()
            total = bal.get("total", {})
            held = {k: v for k, v in total.items() if v}
            print(f"balances    : {held or {'USDT': 0}}")
        except Exception as exc:
            print(f"balances    : unavailable ({exc})")
    return 0 if ok else 1


def _cmd_ingest(args: argparse.Namespace) -> int:
    configure_logging()
    import datetime as dt
    import time

    settings = get_settings()
    symbols = None
    mode = getattr(args, "universe", None) or settings.universe_mode
    if mode == "auto":
        picks = _build_scout(
            settings, top_n=getattr(args, "top", None), timeframe=args.timeframe
        ).select_symbols()
        symbols = picks or None
        print(f"scout selected: {', '.join(picks) if picks else '(none — using watched)'}")
    ingester = MarketDataIngester(timeframe=args.timeframe)
    since = int(time.time() * 1000) - args.days * 86_400_000 if args.days else None
    results = ingester.ingest_all_history(
        since=since, limit=args.limit, max_pages=args.max_pages, symbols=symbols
    )
    for symbol, rows in results.items():
        span = ingester.store.fetch_candles_range(symbol.upper(), args.timeframe)
        if span:
            start = dt.datetime.fromtimestamp(span[0]["ts"] / 1000, dt.UTC).date()
            end = dt.datetime.fromtimestamp(span[-1]["ts"] / 1000, dt.UTC).date()
            print(f"{symbol}: +{rows} new  (stored {len(span)}: {start} → {end})")
        else:
            print(f"{symbol}: +{rows} new")
    return 0


def _cmd_ingest_funding(args: argparse.Namespace) -> int:
    """Pull perpetual funding-rate history into the store (carry track, C1).

    Public data — no futures key needed. Resumes from the newest stored row.
    """
    configure_logging()
    import datetime as dt
    import time

    from rapana.data.ingest import FundingIngester

    settings = get_settings()
    symbols = None
    mode = getattr(args, "universe", None) or settings.universe_mode
    if mode == "auto":
        picks = _build_scout(
            settings, top_n=getattr(args, "top", None), timeframe=args.timeframe
        ).select_symbols()
        symbols = picks or None
        print(f"scout selected: {', '.join(picks) if picks else '(none — using watched)'}")
    ingester = FundingIngester()
    since = int(time.time() * 1000) - args.days * 86_400_000 if args.days else None
    results = ingester.ingest_all(
        since=since, limit=args.limit, max_pages=args.max_pages, symbols=symbols
    )
    for perp, rows in results.items():
        span = ingester.store.fetch_funding_range(perp)
        if span:
            start = dt.datetime.fromtimestamp(span[0]["ts"] / 1000, dt.UTC).date()
            end = dt.datetime.fromtimestamp(span[-1]["ts"] / 1000, dt.UTC).date()
            print(f"{perp}: +{rows} new  (stored {len(span)}: {start} → {end})")
        else:
            print(f"{perp}: +{rows} new")
    return 0


def _cmd_ingest_feargreed(args: argparse.Namespace) -> int:
    """Pull the full daily Fear & Greed history into the store (free, no key)."""
    configure_logging()
    import datetime as dt

    from rapana.feeds.feargreed import fetch_fear_greed_history

    store = _store()
    rows = fetch_fear_greed_history()
    n = store.upsert_macro_series("fear_greed", rows)
    if rows:
        start = dt.datetime.fromtimestamp(rows[0]["ts"] / 1000, dt.UTC).date()
        end = dt.datetime.fromtimestamp(rows[-1]["ts"] / 1000, dt.UTC).date()
        print(f"fear_greed: ingested {n} daily rows  ({start} → {end})")
    else:
        print("fear_greed: no rows returned")
    return 0


def _cmd_scout(args: argparse.Namespace) -> int:
    """Print the deterministic top-N universe the Scout would trade right now."""
    configure_logging()
    settings = get_settings()
    ranked = _build_scout(settings, top_n=args.top, timeframe=args.timeframe).select()
    if not ranked:
        print("scout: no symbols passed the liquidity + momentum screen.")
        return 0
    print(f"=== Scout universe (top {len(ranked)}, {args.timeframe}) ===")
    print(f"{'symbol':<16}{'score':>10}{'$vol(median)':>16}{'momentum':>11}{'vol':>9}")
    for r in ranked:
        print(f"{r.symbol:<16}{r.score:>10.3f}{r.dollar_volume:>16,.0f}"
              f"{r.momentum * 100:>10.2f}%{r.volatility:>9.4f}")
    return 0


def _cmd_journal_verify(args: argparse.Namespace) -> int:
    configure_logging()
    ledger = DecisionLedger()
    ok = ledger.verify_chain()
    entries = len(ledger.read_all())
    print(f"journal entries: {entries}")
    print(f"chain integrity : {'ok' if ok else 'TAMPERED'}")
    return 0 if ok else 1


def _cmd_check_trade(args: argparse.Namespace) -> int:
    """Dry-run a trade proposal through the risk gate (no order placed)."""
    configure_logging()
    settings = get_settings()
    policy = RiskPolicy.from_settings(settings)
    ledger = DecisionLedger()
    ledger.append("trade_proposal", {
        "symbol": args.symbol, "side": args.side,
        "qty": args.qty, "price": args.price, "ref": args.reference,
    })
    proposal = TradeProposal(
        symbol=args.symbol.upper(),
        side=args.side,
        qty=Decimal(str(args.qty)),
        price=Decimal(str(args.price)),
        reference_price=Decimal(str(args.reference)),
    )
    checker = PreTradeChecker(
        policy=policy,
        kill_switch=KillSwitch(settings=settings),
        breaker=CircuitBreaker(policy, starting_equity=Decimal(str(args.equity))),
        equity=Decimal(str(args.equity)),
    )
    decision = checker.check(proposal)
    ledger.append("risk_decision", {"approved": decision.approved, "reason": decision.reason})
    print(f"proposal : {proposal.symbol} {proposal.side} {proposal.qty} @ {proposal.price}")
    print(f"notional : {proposal.notional}")
    print(f"approved : {decision.approved}")
    print(f"reason   : {decision.reason}")
    return 0 if decision.approved else 2


def _cmd_backtest(args: argparse.Namespace) -> int:
    """Fetch OHLCV and backtest a strategy, printing performance metrics."""
    configure_logging()
    import pandas as pd

    settings = get_settings()
    if args.from_store:
        import time

        store = TimeSeriesStore(settings.db_path)
        since = int(time.time() * 1000) - args.days * 86_400_000 if args.days else None
        rows = store.fetch_candles_range(args.symbol.upper(), args.timeframe, since=since)
        if len(rows) < 3:
            raise SystemExit(
                f"Not enough stored candles for {args.symbol} {args.timeframe} "
                f"({len(rows)}). Run `rapana ingest --days N --timeframe {args.timeframe}` first."
            )
        df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    else:
        client = MexcClient(settings=settings)
        client.load_markets()
        raw = client.fetch_ohlcv(args.symbol, timeframe=args.timeframe, limit=args.limit)
        df = pd.DataFrame(raw, columns=["ts", "open", "high", "low", "close", "volume"])

    strat_cls = _STRATEGIES[args.strategy]
    engine = BacktestEngine(BacktestConfig(timeframe=args.timeframe))
    result = engine.run(df, strat_cls(), args.symbol)
    m = result.metrics
    print(f"=== Backtest: {args.symbol} | {args.strategy} | {args.timeframe} ===")
    print(f"bars            : {len(df)}")
    print(f"final equity    : {m.final_equity:.2f}")
    print(f"total return    : {m.total_return * 100:.2f}%")
    print(f"ann. return     : {m.annualized_return * 100:.2f}%")
    print(f"sharpe          : {m.sharpe:.3f}")
    print(f"sortino         : {m.sortino:.3f}")
    print(f"max drawdown    : {m.max_drawdown * 100:.2f}%")
    print(f"volatility      : {m.volatility * 100:.2f}%")
    print(f"trades          : {m.num_trades}")
    print(f"win rate        : {m.win_rate * 100:.1f}%")
    print(f"profit factor   : {m.profit_factor:.2f}")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    """Walk-forward OOS validation + Deflated Sharpe verdict on stored history."""
    configure_logging()
    import time

    import pandas as pd

    from rapana.backtest.validation import holdout_split, validate_config, validate_grid

    settings = get_settings()
    store = TimeSeriesStore(settings.db_path)
    since = int(time.time() * 1000) - args.days * 86_400_000 if args.days else None
    symbols = [args.symbol.upper()] if args.symbol else settings.watch_symbols
    need = args.warmup + args.splits + 3

    data: dict = {}
    for sym in symbols:
        rows = store.fetch_candles_range(sym, args.timeframe, since=since)
        if len(rows) >= need:
            data[sym] = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    if not data:
        raise SystemExit(
            f"Not enough stored history (need >= {need} bars/symbol). Run "
            f"`rapana ingest --days N --timeframe {args.timeframe}` first."
        )

    strategies = {args.strategy: _STRATEGIES[args.strategy]} if args.strategy else dict(_STRATEGIES)
    cfg = BacktestConfig(timeframe=args.timeframe, max_weight=args.max_weight,
                         vol_target=args.vol_target)
    wf_data, hold_data = data, {}
    if args.holdout > 0:
        wf_data, hold_data = {}, {}
        for sym, df in data.items():
            wf_data[sym], hold_data[sym] = holdout_split(df, args.holdout, args.warmup)
    report = validate_grid(
        wf_data, strategies, n_splits=args.splits, warmup=args.warmup,
        timeframe=args.timeframe, config=cfg,
    )

    print(f"=== Walk-forward validation ({args.timeframe}, {report.n_splits} folds, "
          f"warmup {report.warmup}, max_weight {args.max_weight:.2f}) — OUT-OF-SAMPLE only ===")
    print(f"{'config':<22}{'OOS ret':>9}{'OOS Sharpe':>12}{'folds+':>8}{'worst':>9}{'bars':>7}")
    for c in sorted(report.configs, key=lambda c: c.oos_sharpe_bar, reverse=True):
        print(f"{c.label:<22}{c.oos_return * 100:>8.2f}%{c.oos_sharpe_annual:>12.2f}"
              f"{c.pct_folds_positive * 100:>7.0f}%{c.worst_fold_return * 100:>8.2f}%{c.n_obs:>7}")

    print("\n=== Selection-bias-corrected verdict (Deflated Sharpe Ratio) ===")
    print(f"trials evaluated : {report.n_trials}  (raw config count; correlated configs "
          "not yet de-duplicated, so the DSR is conservative)")
    if report.best is not None:
        print(f"best config      : {report.best.label}  (OOS Sharpe {report.best.oos_sharpe_annual:.2f} ann)")
        print(f"OOS return       : {report.best.oos_return * 100:.2f}%   vs HODL {report.hodl_return * 100:.2f}%")
        print(f"deflated Sharpe  : {report.deflated_sharpe:.3f}   (credible if > 0.95)")
        print(f"VERDICT          : {'PASS' if report.passed else 'FAIL'}  "
              "(PASS = DSR > 0.95 AND beats buy & hold)")
        if not report.passed:
            print("                   no tradable edge — do not risk real money on this.")

    if args.holdout > 0 and report.best is not None:
        b = report.best
        hr = validate_config(
            hold_data[b.symbol], _STRATEGIES[b.strategy], b.symbol,
            n_splits=1, warmup=args.warmup, timeframe=args.timeframe, config=cfg,
        )
        print(f"\n=== LOCKED HOLDOUT (final {args.holdout * 100:.0f}%, evaluated ONCE) ===")
        if hr is not None:
            print(f"{b.label}: OOS return {hr.oos_return * 100:.2f}%  "
                  f"OOS Sharpe {hr.oos_sharpe_annual:.2f}  ({hr.n_obs} bars)")
        else:
            print("insufficient holdout history to evaluate the best config.")
    return 0


def _csv_ints(raw: str, name: str) -> tuple[int, ...]:
    try:
        vals = tuple(int(x.strip()) for x in raw.split(",") if x.strip())
    except ValueError as exc:
        raise SystemExit(f"{name} must be a comma-separated list of integers") from exc
    if not vals or any(v < 1 for v in vals):
        raise SystemExit(f"{name} must contain one or more positive integers")
    return vals


def _csv_xs_signals(raw: str):
    allowed = {"momentum", "reversion", "funding_rank"}
    vals = tuple(x.strip() for x in raw.split(",") if x.strip())
    bad = [v for v in vals if v not in allowed]
    if not vals or bad:
        raise SystemExit(
            "--signals must be a comma-separated subset of: "
            + ", ".join(sorted(allowed))
            + (f" (invalid: {', '.join(bad)})" if bad else "")
        )
    return vals


def _cmd_validate_xs(args: argparse.Namespace) -> int:
    """Cross-sectional relative-strength rotation + Deflated Sharpe verdict."""
    configure_logging()
    import time

    from rapana.backtest.cross_sectional import (
        load_store_funding,
        load_store_universe,
        validate_cross_sectional_grid,
    )

    settings = get_settings()
    store = TimeSeriesStore(settings.db_path)
    since = int(time.time() * 1000) - args.days * 86_400_000 if args.days else None
    data = load_store_universe(store, args.timeframe, since=since)
    need = args.warmup + args.splits + 3
    short = [f"{sym} ({len(df)})" for sym, df in data.items() if len(df) < need]
    if short:
        raise SystemExit(
            f"Not enough stored history for all symbols (need >= {need} bars each). "
            f"Short: {', '.join(short)}. Run `rapana ingest --timeframe {args.timeframe} --days N` first."
        )

    signals = _csv_xs_signals(args.signals)
    funding = (
        load_store_funding(store, list(data), since=None)
        if "funding_rank" in signals else None
    )
    cfg = BacktestConfig(timeframe=args.timeframe, max_weight=args.max_weight,
                         fee_pct=Decimal(str(args.fee)))
    report = validate_cross_sectional_grid(
        data,
        signals=signals,
        lookbacks=_csv_ints(args.lookbacks, "--lookbacks"),
        top_ks=_csv_ints(args.top_ks, "--top-ks"),
        rebalances=_csv_ints(args.rebalances, "--rebalances"),
        n_splits=args.splits,
        warmup=args.warmup,
        timeframe=args.timeframe,
        config=cfg,
        funding_by_symbol=funding,
    )

    print(f"=== Cross-sectional validation ({args.timeframe}, {report.n_splits} folds, "
          f"warmup {report.warmup}, {len(data)} symbols, max_weight {args.max_weight:.2f}) "
          "— POINT-IN-TIME, OOS ===")
    print(f"signals          : {', '.join(signals)}")
    print(f"cost model       : taker fee {args.fee * 1e4:.1f}bp per traded notional")
    print(f"{'config':<34}{'OOS ret':>9}{'OOS Sharpe':>12}{'folds+':>8}{'worst':>9}{'bars':>7}")
    for c in sorted(report.configs, key=lambda c: c.oos_sharpe_bar, reverse=True):
        print(f"{c.strategy:<34}{c.oos_return * 100:>8.2f}%{c.oos_sharpe_annual:>12.2f}"
              f"{c.pct_folds_positive * 100:>7.0f}%{c.worst_fold_return * 100:>8.2f}%{c.n_obs:>7}")

    print("\n=== Selection-bias-corrected verdict (Deflated Sharpe Ratio) ===")
    print(f"trials evaluated : {report.n_trials}  (signal x lookback x top-k x rebalance)")
    if report.best is not None:
        print(f"best config      : {report.best.strategy}  "
              f"(OOS Sharpe {report.best.oos_sharpe_annual:.2f} ann)")
        print(f"OOS return       : {report.best.oos_return * 100:.2f}%   "
              f"vs equal-weight HODL {report.hodl_return * 100:.2f}%")
        print(f"deflated Sharpe  : {report.deflated_sharpe:.3f}   (credible if > 0.95)")
        print(f"VERDICT          : {'PASS' if report.passed else 'FAIL'}  "
              "(PASS = DSR > 0.95 AND beats equal-weight HODL)")
        if not report.passed:
            print("                   no tradable cross-sectional price edge by this gate.")
    return 0


def _cmd_validate_carry(args: argparse.Namespace) -> int:
    """Funding-rate carry walk-forward + Deflated Sharpe verdict, benchmarked vs CASH.

    The go/no-go gate (C2): does a delta-neutral short-perp + long-spot book
    beat cash, net of all costs, out-of-sample? Reads stored funding history.
    """
    configure_logging()
    import time

    from rapana.backtest.carry import CarryConfig, validate_carry_grid
    from rapana.mexc.client import to_perp_symbol

    settings = get_settings()
    store = TimeSeriesStore(settings.db_path)
    since = int(time.time() * 1000) - args.days * 86_400_000 if args.days else None
    need = args.warmup + args.splits + 3
    want = [to_perp_symbol(args.symbol)] if args.symbol else store.funding_symbols()

    funding_by_symbol: dict = {}
    for perp in want:
        rows = store.fetch_funding_range(perp, since=since)
        if len(rows) >= need:
            funding_by_symbol[perp] = rows
    if not funding_by_symbol:
        raise SystemExit(
            f"Not enough stored funding history (need >= {need} intervals/symbol). "
            "Run `rapana ingest-funding --days N` first."
        )

    cfg = CarryConfig(
        fee_pct=args.fee, slippage_pct=args.slippage, basis_drag_bps=args.basis_drag_bps
    )
    report = validate_carry_grid(
        funding_by_symbol, n_splits=args.splits, warmup=args.warmup,
        cfg=cfg, cash_return=args.cash_return,
    )

    rt_cost = 2.0 * (args.fee + args.slippage) * 2.0  # entry + exit, both legs
    print(f"=== Carry validation ({report.funding_interval_hours:.0f}h funding, "
          f"{report.n_splits} folds, warmup {report.warmup}) — DELTA-NEUTRAL, OOS ===")
    print(f"cost model       : {args.fee * 1e4:.1f}bp fee + {args.slippage * 1e4:.1f}bp slip "
          f"per leg  →  {rt_cost * 1e4:.0f}bp round-trip; {args.basis_drag_bps:.1f}bp/interval drag")
    print(f"{'config':<22}{'OOS net':>9}{'gross':>9}{'OOS Sharpe':>12}{'folds+':>8}{'held':>7}{'bars':>7}")
    for c in sorted(report.configs, key=lambda c: c.oos_sharpe_bar, reverse=True):
        held = sum(f.pct_held for f in c.folds) / len(c.folds) if c.folds else 0.0
        print(f"{c.label:<22}{c.oos_return * 100:>8.2f}%{c.gross_funding * 100:>8.2f}%"
              f"{c.oos_sharpe_annual:>12.2f}{c.pct_intervals_positive * 100:>7.0f}%"
              f"{held * 100:>6.0f}%{c.n_obs:>7}")

    print("\n=== Selection-bias-corrected verdict (Deflated Sharpe Ratio) ===")
    print(f"trials evaluated : {report.n_trials}  (symbol x policy)")
    if report.best is not None:
        b = report.best
        print(f"best config      : {b.label}  (OOS Sharpe {b.oos_sharpe_annual:.2f} ann)")
        print(f"OOS net carry    : {b.oos_return * 100:.2f}%   "
              f"(gross funding {b.gross_funding * 100:.2f}%, costs ate "
              f"{(b.gross_funding - b.oos_return) * 100:.2f}%)  vs CASH {report.cash_return * 100:.2f}%")
        print(f"deflated Sharpe  : {report.deflated_sharpe:.3f}   (credible if > 0.95)")
        print(f"VERDICT          : {'PASS' if report.passed else 'FAIL'}  "
              "(PASS = DSR > 0.95 AND beats cash net of costs)")
        if not report.passed:
            print("                   no tradable carry edge — do not risk real money on this.")
    return 0


def _cmd_validate_funding_spike(args: argparse.Namespace) -> int:
    """Funding-spike reversion event study + Deflated Sharpe verdict, vs CASH.

    Event-driven study #1: does fading an extreme funding rate (the contrarian
    side of crowded positioning) earn a short-horizon price reversion — plus the
    funding the faded side receives — net of costs, out-of-sample? Joins stored
    funding to stored price; run `ingest-funding` AND `ingest` first.
    """
    configure_logging()
    import time

    from rapana.backtest.funding_spike import (
        FundingSpikeConfig,
        align_funding_price,
        validate_funding_spike_grid,
    )
    from rapana.mexc.client import to_perp_symbol

    settings = get_settings()
    store = TimeSeriesStore(settings.db_path)
    since = int(time.time() * 1000) - args.days * 86_400_000 if args.days else None
    need = args.warmup + args.splits + 3
    want = [to_perp_symbol(args.symbol)] if args.symbol else store.funding_symbols()

    data_by_symbol: dict = {}
    skipped: list[str] = []
    for perp in want:
        funding = store.fetch_funding_range(perp, since=since)
        if len(funding) < need:
            continue
        spot = perp.split(":")[0]  # BTC/USDT:USDT -> BTC/USDT
        candles = store.fetch_candles_range(spot, args.timeframe, since=since)
        if len(candles) < 2:
            skipped.append(f"{perp} (no {args.timeframe} price for {spot})")
            continue
        kept, closes = align_funding_price(funding, candles)
        if len(kept) >= need:
            data_by_symbol[perp] = (kept, closes)
        else:
            skipped.append(f"{perp} (only {len(kept)} priced funding pts)")

    if not data_by_symbol:
        raise SystemExit(
            f"Not enough joined funding+price (need >= {need} intervals/symbol). Run "
            f"`rapana ingest-funding --days N` AND "
            f"`rapana ingest --days N --timeframe {args.timeframe}` first."
            + (f"\nskipped: {'; '.join(skipped)}" if skipped else "")
        )

    cfg = FundingSpikeConfig(fee_pct=args.fee, slippage_pct=args.slippage)
    report = validate_funding_spike_grid(
        data_by_symbol, n_splits=args.splits, warmup=args.warmup,
        cfg=cfg, cash_return=args.cash_return,
    )

    rt_cost = 2.0 * (args.fee + args.slippage)  # entry + exit, single leg
    print(f"=== Funding-spike validation ({report.funding_interval_hours:.0f}h funding, "
          f"{report.n_splits} folds, warmup {report.warmup}) — CONTRARIAN FADE, OOS ===")
    print(f"cost model       : {args.fee * 1e4:.1f}bp fee + {args.slippage * 1e4:.1f}bp slip "
          f"per side  →  {rt_cost * 1e4:.0f}bp round-trip")
    print(f"symbols joined   : {', '.join(data_by_symbol)}")
    if skipped:
        print(f"skipped          : {'; '.join(skipped)}")
    print(f"{'config':<22}{'OOS net':>9}{'price':>9}{'funding':>9}{'OOS Sharpe':>12}"
          f"{'int+':>7}{'events':>8}{'bars':>7}")
    for c in sorted(report.configs, key=lambda c: c.oos_sharpe_bar, reverse=True):
        print(f"{c.label:<22}{c.oos_return * 100:>8.2f}%{c.gross_price * 100:>8.2f}%"
              f"{c.gross_funding * 100:>8.2f}%{c.oos_sharpe_annual:>12.2f}"
              f"{c.pct_intervals_positive * 100:>6.0f}%{c.n_events:>8}{c.n_obs:>7}")

    print("\n=== Selection-bias-corrected verdict (Deflated Sharpe Ratio) ===")
    print(f"trials evaluated : {report.n_trials}  (symbol x policy)")
    if report.best is not None:
        b = report.best
        print(f"best config      : {b.label}  (OOS Sharpe {b.oos_sharpe_annual:.2f} ann)")
        print(f"OOS net          : {b.oos_return * 100:.2f}%   "
              f"(price {b.gross_price * 100:+.2f}%, funding {b.gross_funding * 100:+.2f}%, "
              f"costs {b.total_costs * 100:.2f}%)  vs CASH {report.cash_return * 100:.2f}%")
        print(f"deflated Sharpe  : {report.deflated_sharpe:.3f}   (credible if > 0.95)")
        print(f"VERDICT          : {'PASS' if report.passed else 'FAIL'}  "
              "(PASS = DSR > 0.95 AND beats cash net of costs)")
        if b.gross_price <= 0 < b.gross_funding:
            print("                   NOTE: edge is funding, not reversion (price leg "
                  "<= 0) — that is disguised carry, which already failed C2.")
        if not report.passed:
            print("                   no tradable reversion edge — do not risk real money on this.")
    return 0


def _cmd_validate_universe(args: argparse.Namespace) -> int:
    """Point-in-time Scout-vs-fixed-majors walk-forward + Deflated Sharpe verdict."""
    configure_logging()
    import time

    import pandas as pd

    from rapana.universe.ranker import UniverseParams, bars_per_day_for
    from rapana.universe.validation import validate_universe

    settings = get_settings()
    store = TimeSeriesStore(settings.db_path)
    since = int(time.time() * 1000) - args.days * 86_400_000 if args.days else None
    need = args.warmup + args.splits + 3
    candidates: dict = {}
    for sym in store.symbols(args.timeframe):
        rows = store.fetch_candles_range(sym, args.timeframe, since=since)
        if len(rows) >= need:
            candidates[sym] = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    if len(candidates) < 2:
        raise SystemExit(
            f"Need >= 2 candidate symbols with >= {need} bars. Run "
            f"`rapana ingest --universe auto --timeframe {args.timeframe} --days N` first."
        )
    params = UniverseParams(
        top_n=args.top or settings.universe_top_n,
        min_quote_volume_usd=settings.universe_min_quote_volume_usd,
        momentum_lookback=settings.universe_momentum_lookback,
        bars_per_day=bars_per_day_for(args.timeframe),
    )
    report = validate_universe(
        candidates, _STRATEGIES[args.strategy], params,
        n_splits=args.splits, warmup=args.warmup, timeframe=args.timeframe,
        config=BacktestConfig(timeframe=args.timeframe, max_weight=args.max_weight,
                              vol_target=args.vol_target),
        benchmark_symbols=settings.watch_symbols,
    )
    print(f"=== Universe validation ({args.timeframe}, {report.n_splits} folds, "
          f"warmup {report.warmup}, strategy {args.strategy}, max_weight {args.max_weight:.2f}) "
          "— POINT-IN-TIME, OOS ===")
    print(f"candidates evaluated : {report.n_candidates}")
    print(f"{'arm':<10}{'OOS ret':>10}{'OOS Sharpe':>12}{'folds+':>8}{'worst':>9}{'bars':>7}")
    for arm in (report.scout, report.benchmark):
        if arm is None:
            continue
        print(f"{arm.strategy:<10}{arm.oos_return * 100:>9.2f}%{arm.oos_sharpe_annual:>12.2f}"
              f"{arm.pct_folds_positive * 100:>7.0f}%{arm.worst_fold_return * 100:>8.2f}%{arm.n_obs:>7}")
    arms = {a.strategy: a for a in (report.scout, report.benchmark) if a is not None}
    best_arm = arms.get(report.best_label)
    best_ret = best_arm.oos_return if best_arm is not None else 0.0
    print(f"\nbest arm        : {report.best_label}  "
          f"(OOS {best_ret * 100:.2f}% vs HODL majors {report.hodl_return * 100:.2f}%)")
    print(f"deflated Sharpe : {report.deflated_sharpe:.3f}   (credible if > 0.95)")
    print(f"VERDICT         : {'PASS' if report.passed else 'FAIL'}  "
          "(PASS = DSR > 0.95 AND beats HODL majors)")
    print("(DSR is arm-level — scout-rule vs fixed-majors — not a correction for "
          "all design/parameter choices.)")
    print(f"\n{report.survivorship_warning}")
    return 0


def _print_hunt_report(report, args, bars, symbols, timeframe) -> None:
    """Shared drift-adjusted verdict table for `hunt` and `hunt-funding`."""
    mode = "pooled (1 trial/trigger, events merged)" if args.pooled else "per-symbol exploratory"
    print(f"=== Trigger hunt [{mode}] ({timeframe}, {report.n_trials} trials, {bars} bars, "
          f"{symbols}) ===")
    survivor_note = (
        "* = PASS survivor (drift-adjusted)"
        if report.pass_eligible
        else "exploratory only; PASS requires pooled hunt or locked confirm holdout"
    )
    print(f"  fee/side={args.fee}  slip/side={args.slippage}  splits={args.splits}  "
          f"warmup={args.warmup}  {survivor_note}")
    print(f"  {'trigger':<26} {'sym':<10} {'nOOS':>4} {'meanNet':>9} {'drift':>9} "
          f"{'excess':>9} {'win%':>6} {'skillDSR':>9}")
    for v in report.verdicts:
        flag = (
            " *"
            if report.pass_eligible and v.deflated_skill_sharpe > args.dsr and v.excess > 0.0
            else ""
        )
        print(f"  {v.trigger:<26} {v.symbol:<10} {v.n_oos:>4} "
              f"{v.mean_net * 100:>8.3f}% {v.drift * 100:>8.3f}% {v.excess * 100:>8.3f}% "
              f"{v.win_rate * 100:>5.1f}% {v.deflated_skill_sharpe:>9.3f}{flag}")
    print()
    if report.passed:
        for s in report.survivors:
            print(f"  SURVIVOR: {s.label}  skillDSR={s.deflated_skill_sharpe:.3f}  "
                  f"excess={s.excess * 100:.3f}%  win={s.win_rate * 100:.1f}%  ({s.n_oos} OOS events)")
        print(f"\n  VERDICT: PASS — {len(report.survivors)} survivor(s) beat drift at DSR > {args.dsr}.")
    else:
        best = report.best
        bmsg = (f" best={best.label} skillDSR={best.deflated_skill_sharpe:.3f} "
                f"excess={best.excess * 100:.3f}%" if best else " no scorable trigger")
        print(f"  VERDICT: FAIL — no trigger beat drift at DSR > {args.dsr}.{bmsg}")
        print("  (skillDSR corrects for bull-market drift; most triggers die here.)")
        if not report.pass_eligible:
            print("  (per-symbol output is exploratory and cannot PASS without pooled or locked holdout confirmation.)")


def _cmd_hunt(args: argparse.Namespace) -> int:
    """Alpha hunt: test every event trigger over stored OHLCV and rank by DSR."""
    configure_logging()
    import time

    import pandas as pd

    from rapana.triggers import DEFAULT_TRIGGERS, run_hunt, run_pooled_hunt

    settings = get_settings()
    store = _store()
    timeframe = args.timeframe
    symbols = [args.symbol.upper()] if args.symbol else settings.watch_symbols
    since = int(time.time() * 1000) - args.days * 86_400_000 if args.days else None
    data: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        rows = store.fetch_candles_range(sym, timeframe, since=since)
        if len(rows) < 3:
            print(f"  skip {sym}: not enough stored candles (run `rapana ingest` first)")
            continue
        data[sym] = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    if not data:
        raise SystemExit(f"No stored candles found. Run `rapana ingest --timeframe {timeframe}` first.")

    triggers = list(DEFAULT_TRIGGERS)
    fg_rows = store.fetch_macro_series("fear_greed")
    if fg_rows:
        from rapana.triggers.macro_triggers import FearGreedExtreme

        triggers += [
            FearGreedExtreme(fg_rows, 25.0, 75.0, 5),
            FearGreedExtreme(fg_rows, 20.0, 80.0, 5),
            FearGreedExtreme(fg_rows, 25.0, 75.0, 10),
        ]
        print(f"  fear_greed: {len(fg_rows)} daily rows stored -> F&G triggers enabled")

    report = (
        run_pooled_hunt(data, triggers,
                        timeframe=timeframe, n_splits=args.splits, warmup=args.warmup,
                        fee_per_side=args.fee, slippage_per_side=args.slippage,
                        min_oos=args.min_events, dsr_threshold=args.dsr)
        if args.pooled
        else run_hunt(data, triggers,
                      timeframe=timeframe, n_splits=args.splits, warmup=args.warmup,
                      fee_per_side=args.fee, slippage_per_side=args.slippage,
                      min_oos=args.min_events, dsr_threshold=args.dsr)
    )

    bars = sum(len(df) for df in data.values())
    _print_hunt_report(report, args, bars, list(data), timeframe)
    return 0


def _cmd_hunt_funding(args: argparse.Namespace) -> int:
    """Alpha hunt on the perp funding grid: test funding event triggers."""
    configure_logging()
    import pandas as pd

    from rapana.triggers.funding_triggers import FUNDING_TRIGGERS, build_funding_frame
    from rapana.triggers.study import run_hunt, run_pooled_hunt

    settings = get_settings()
    store = _store()
    timeframe = args.timeframe
    data: dict[str, pd.DataFrame] = {}
    for spot in settings.watch_symbols:
        perp = spot.upper() + ":USDT"
        frame = build_funding_frame(store, perp, spot.upper(), timeframe)
        if frame is None or len(frame) < 10:
            print(f"  skip {perp}: not enough stored funding (run `rapana ingest-funding`)")
            continue
        data[perp] = frame
    if not data:
        raise SystemExit("No funding data found. Run `rapana ingest-funding` first.")

    report = (
        run_pooled_hunt(data, list(FUNDING_TRIGGERS),
                        timeframe=timeframe, n_splits=args.splits, warmup=args.warmup,
                        fee_per_side=args.fee, slippage_per_side=args.slippage,
                        min_oos=args.min_events, dsr_threshold=args.dsr)
        if args.pooled
        else run_hunt(data, list(FUNDING_TRIGGERS),
                      timeframe=timeframe, n_splits=args.splits, warmup=args.warmup,
                      fee_per_side=args.fee, slippage_per_side=args.slippage,
                      min_oos=args.min_events, dsr_threshold=args.dsr)
    )
    bars = sum(len(df) for df in data.values())
    _print_hunt_report(report, args, bars, list(data), f"{timeframe} (funding grid)")
    return 0


def _cmd_confirm(args: argparse.Namespace) -> int:
    """Single-hypothesis confirmation of a breakout lead: sweep on the dev set,
    then test the top config on a LOCKED holdout it never saw.

    The sweep is exploratory (read its numbers as N-trial); the holdout is the
    one honest single test. CONFIRMED only if the holdout shows positive excess
    AND a credible solo skill DSR.
    """
    configure_logging()
    import pandas as pd

    from rapana.backtest.engine import BARS_PER_YEAR
    from rapana.backtest.validation import holdout_split
    from rapana.triggers.ohlcv_triggers import BreakoutLong
    from rapana.triggers.study import solo_skill_dsr, study_trigger

    store = _store()
    tf = args.timeframe
    rows = store.fetch_candles_range(args.symbol.upper(), tf)
    if len(rows) < 100:
        raise SystemExit(
            f"Not enough {tf} data for {args.symbol} (run `rapana ingest --timeframe {tf} --days 2000`)."
        )
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    bpy = BARS_PER_YEAR.get(tf, 365)
    lookbacks = [int(x) for x in args.lookbacks.split(",") if x.strip()]
    horizons = [int(x) for x in args.horizons.split(",") if x.strip()]
    warm = max(max(lookbacks), 20)

    print(f"=== Confirm: {args.symbol} breakout_long sweep [{tf}, {len(df)} bars] ===")
    print("  (exploratory dev sweep — read as multi-trial, NOT single-hypothesis)")
    print(f"  {'L':>4} {'H':>3} {'nOOS':>5} {'meanNet':>9} {'drift':>9} {'excess':>9} "
          f"{'win%':>6} {'soloSkill':>9}")
    dev = []
    for L in lookbacks:
        for H in horizons:
            v = study_trigger(df, BreakoutLong(L, H), args.symbol, n_splits=args.splits,
                              warmup=warm, fee_per_side=args.fee, slippage_per_side=args.slippage,
                              bars_per_year=bpy)
            if v is None or v.n_oos < args.min_events:
                continue
            d = solo_skill_dsr(v)
            print(f"  {L:>4} {H:>3} {v.n_oos:>5} {v.mean_net * 100:>8.3f}% {v.drift * 100:>8.3f}% "
                  f"{v.excess * 100:>8.3f}% {v.win_rate * 100:>5.1f}% {d:>9.3f}")
            dev.append((v.excess, v, L, H))
    if not dev:
        print("  no configs scored enough events.")
        return 0

    # Pre-registered selection rule: the highest-excess config in the dev sweep.
    dev.sort(reverse=True, key=lambda r: r[0])
    _, best, bL, bH = dev[0]
    print(f"\n  selected (top dev excess): L={bL} H={bH}  excess={best.excess * 100:.3f}%  "
          f"win={best.win_rate * 100:.1f}%")

    wf, hold = holdout_split(df, args.holdout, warmup=warm)
    print(f"\n=== Locked holdout ({args.holdout * 100:.0f}% held out, never tuned on) — "
          f"THE single-hypothesis test ===")
    survived = True
    for label, sl in (("walk-forward (dev)", wf), ("HOLDOUT (locked)", hold)):
        v = study_trigger(sl, BreakoutLong(bL, bH), args.symbol, n_splits=args.splits,
                          warmup=warm, fee_per_side=args.fee, slippage_per_side=args.slippage,
                          bars_per_year=bpy)
        if v is None or v.n_oos < args.min_events:
            print(f"  {label:<22} too few events")
            if "HOLDOUT" in label:
                survived = False
            continue
        d = solo_skill_dsr(v)
        ok = v.excess > 0.0 and d > args.dsr
        if "HOLDOUT" in label:
            survived = ok
        flag = "  <-- PASS" if ok else ""
        print(f"  {label:<22} nOOS={v.n_oos:>4} excess={v.excess * 100:>8.3f}% "
              f"win={v.win_rate * 100:>5.1f}% soloSkillDSR={d:>7.3f}{flag}")

    if survived:
        print(f"\n  VERDICT: CONFIRMED — {args.symbol} breakout_long(L={bL},H={bH}) beats drift "
              f"out-of-holdout at solo DSR > {args.dsr}. Candidate for paper deployment.")
    else:
        print("\n  VERDICT: NOT CONFIRMED — fails the locked holdout. The dev excess was "
              "overfit / noise; do not deploy.")
    return 0


def _cmd_run_fleet(args: argparse.Namespace) -> int:
    """Run one fleet decision cycle (paper mode by default)."""
    configure_logging()
    settings = get_settings()
    client = MexcClient(settings=settings) if settings.is_live else None
    mode = getattr(args, "universe", None) or settings.universe_mode
    scout = None
    symbols = settings.watch_symbols
    if mode == "auto":
        # One-shot: select once, ingest exactly those, trade them this cycle (no
        # in-fleet re-selection, so the ingested set == the traded set).
        scout = _build_scout(settings, top_n=getattr(args, "top", None))
        symbols = scout.select_symbols() or settings.watch_symbols
        print(f"scout selected: {', '.join(symbols)}")
    provider = StoreDataProvider(
        store=_store(),  # type: ignore[arg-type]
        client=client,
    )
    # Ensure fresh data for the (possibly auto-selected) universe
    MarketDataIngester(client=client, store=_store(), settings=settings).ingest_all(symbols=symbols)
    ledger = DecisionLedger()
    auditor = ComplianceAuditor(ledger)
    capital = StagedCapital(paper=not settings.is_live)
    trader = ExecutionTrader(
        PaperExecutor(
            execution_mode=settings.execution_mode,
            paper_maker_fill_fraction=settings.paper_maker_fill_fraction,
        ),
        capital,
    )
    fleet = Fleet(
        provider=provider,
        capital=capital,
        trader=trader,
        auditor=auditor,
        settings=settings,
        config=FleetConfig(symbols=symbols),
    )
    state = fleet.run_cycle()
    print(state.digest)
    print(f"\nequity : {state.equity:.2f}  |  cash: {state.cash:.2f}  |  positions: "
          f"{ {k: float(v) for k, v in state.positions.items() if v} }")
    return 0


def _store():
    from rapana.data.store import TimeSeriesStore

    return TimeSeriesStore(get_settings().db_path)


def _build_scout(settings, *, top_n=None, timeframe: str = "1h"):
    """Build a Scout from settings (with optional top_n override)."""
    from rapana.mexc.client import MexcClient
    from rapana.universe.ranker import UniverseParams, bars_per_day_for
    from rapana.universe.scout import Scout

    params = UniverseParams(
        top_n=top_n or settings.universe_top_n,
        min_quote_volume_usd=settings.universe_min_quote_volume_usd,
        momentum_lookback=settings.universe_momentum_lookback,
        bars_per_day=bars_per_day_for(timeframe),
    )
    return Scout(
        MexcClient(settings=settings), params,
        timeframe=timeframe, candidate_k=settings.universe_candidate_k,
    )


def _build_paper_fleet(
    settings=None,
    initial=Decimal("10000"),
    *,
    scout=None,
    universe_mode="fixed",
    ledger_path=None,
    state_path=None,
    notifier=None,
    allow_live_feeds: bool = True,
):
    """Assemble a paper fleet + runner + notifier for CLI use."""

    settings = settings or get_settings()
    from rapana.data.store import TimeSeriesStore

    store = TimeSeriesStore(settings.db_path)
    provider = StoreDataProvider(store=store)
    ledger = DecisionLedger(path=ledger_path)
    auditor = ComplianceAuditor(ledger)
    capital = StagedCapital(paper=True)
    trader = ExecutionTrader(
        PaperExecutor(
            execution_mode=settings.execution_mode,
            paper_maker_fill_fraction=settings.paper_maker_fill_fraction,
        ),
        capital,
    )
    # Historical replay must NEVER consume live external feeds: a "now"
    # sentiment/premium reading leaking into a past bar is lookahead bias, which
    # would silently invalidate every replay/backtest number. Forward paper/live
    # (allow_live_feeds=True) lets the orchestrator wire them from settings.
    analysts = None
    if not allow_live_feeds:
        from rapana.agents import MacroAnalyst, MarketAnalyst, SentimentAnalyst

        analysts = [
            MarketAnalyst(timeframe="1h"),
            SentimentAnalyst(),
            MacroAnalyst(),
        ]
    fleet = Fleet(
        provider=provider, capital=capital, trader=trader, auditor=auditor,
        settings=settings,
        config=FleetConfig(
            symbols=settings.watch_symbols, universe_mode=universe_mode,
            rebalance_bars=settings.universe_rebalance_bars,
        ),
        analysts=analysts,
        scout=scout,
        initial_equity=initial,
    )
    perf = PerformanceTracker(
        initial_equity=initial,
        benchmark_cash_return=settings.benchmark_cash_return,
    )
    autopilot = Autopilot(
        AutopilotPolicy.from_settings(settings), capital, perf, notifier=build_notifier(settings),
        kill_switch=fleet.kill_switch,
    )
    runner = FleetRunner(
        fleet,
        perf,
        notifier=notifier or build_notifier(settings),
        state_path=state_path or settings.state_path,
        autopilot=autopilot,
    )
    return fleet, runner, store


def _has_mexc_key() -> bool:
    # Consistent with mexc.get_keys(): check the secrets provider (OS env AND the
    # .env file), not just os.environ, so keys configured only in .env are
    # detected. Otherwise replay would silently fall back to synthetic data.
    from rapana.secrets import get_secrets_provider

    provider = get_secrets_provider()
    return bool(provider.get("MEXC_API_KEY") and provider.get("MEXC_API_SECRET"))


def _cmd_replay(args: argparse.Namespace) -> int:
    """Decision-making backtest: run the WHOLE fleet over data and watch it decide.

    Data source: live MEXC OHLCV (requires a read-only key), or ``--from-store``
    to replay ingested history (no key needed), or ``--synthetic`` for generated
    data. With no key and none of those flags it fails loudly rather than
    silently using synthetic. ``--trace`` prints a sampled decision trace
    (signals -> debate -> proposal -> risk verdict) per bar.
    """
    configure_logging()
    import pandas as pd

    settings = get_settings()
    # Synthetic data is strictly opt-in via --synthetic. Without a MEXC key (and
    # not reading from the local store) we fail loudly rather than silently
    # backtesting on generated data (which would produce meaningless results).
    if not args.synthetic and not args.from_store and not _has_mexc_key():
        raise SystemExit(
            "No MEXC API key found. Set MEXC_API_KEY and MEXC_API_SECRET in your "
            "environment or .env (read-only key, NO withdraw), pass --from-store to "
            "replay ingested history, or --synthetic for generated data."
        )
    use_synthetic = args.synthetic

    if use_synthetic:
        from rapana.data.synthetic import make_synthetic_ohlcv

        data = make_synthetic_ohlcv(settings.watch_symbols, bars=args.limit)
        bars_available = args.limit
        source = "synthetic"
    elif args.from_store:
        import time

        store = TimeSeriesStore(settings.db_path)
        since = int(time.time() * 1000) - args.days * 86_400_000 if args.days else None
        data = {}
        for sym in settings.watch_symbols:
            rows = store.fetch_candles_range(sym.upper(), args.timeframe, since=since)
            data[sym] = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
        bars_available = min((len(df) for df in data.values()), default=0)
        if bars_available < 3:
            raise SystemExit(
                "Not enough stored candles to replay. Run "
                f"`rapana ingest --days N --timeframe {args.timeframe}` first."
            )
        source = "stored MEXC"
    else:
        client = MexcClient(settings=settings)
        client.load_markets()
        data = {}
        for sym in settings.watch_symbols:
            raw = client.fetch_ohlcv(sym, timeframe=args.timeframe, limit=args.limit)
            data[sym] = pd.DataFrame(raw, columns=["ts", "open", "high", "low", "close", "volume"])
        bars_available = min((len(df) for df in data.values()), default=0)
        source = "MEXC"

    initial = Decimal(str(args.equity))
    if args.maker_eval:
        report = _run_paired_maker_eval(data, settings, initial, args)
        print(f"=== Decision backtest ({source} data, "
              f"{bars_available} bars, {settings.watch_symbols}) ===")
        print(format_paper_maker_eval_report(report))
        return 0

    provider = ReplayProvider(data)
    fleet, runner, _ = _build_paper_fleet(settings, initial=initial, allow_live_feeds=False)
    fleet.provider = provider  # swap in the replay provider

    trace_every = args.trace_every if args.trace else 0

    def progress(i, total):
        if i % max(1, total // 10) == 0 or i == total:
            pct = i / total * 100
            eq = runner.performance.equity_series[-1] if runner.performance.equity_series else initial
            print(f"  replay {i}/{total} ({pct:.0f}%)  equity={eq}")

    def trace(bar, state):
        if not trace_every or bar % trace_every != 0:
            return
        for sym, ss in state.symbols.items():
            top = max(ss.signals, key=lambda s: abs(s.strength) * s.confidence) if ss.signals else None
            prop = (
                f"{ss.proposal.side} {ss.proposal.qty}@{ss.proposal.price:.2f}"
                if ss.proposal else "hold"
            )
            verdict = (
                f"{'OK' if ss.risk_decision.approved else 'VETO:' + ss.risk_decision.reason}"
                if ss.risk_decision else "-"
            )
            top_s = f"{top.source}:{top.direction}({top.strength:+.2f})" if top else "-"
            print(
                f"  [bar {bar:>4}] {sym:<9} px={float(ss.price):<10.2f} "
                f"sig={top_s:<22} bull/bear={ss.bull.score:+.2f}/{ss.bear.score:+.2f} "
                f"-> {prop:<22} risk={verdict}"
            )

    print(f"=== Decision backtest ({source} data, "
          f"{bars_available} bars, {settings.watch_symbols}) ===")
    summary = runner.run_replay(
        provider, bars_per_day=args.bars_per_day, warmup=args.warmup,
        on_progress=progress, on_cycle=trace,
    )
    print(f"\n=== Replay summary ({settings.watch_symbols}) ===")
    for k, v in summary.items():
        print(f"  {k:<16}: {v}")
    analytics = fleet.memory.analytics()
    if analytics:
        print("\n=== Analyst accuracy (reflection loop) ===")
        for src, stats in analytics.items():
            print(f"  {src:<10}: acc={stats['accuracy']} weight={fleet.memory.weight(src):.2f} ({stats['total']} calls)")
    return 0


def _run_paired_maker_eval(data: dict, settings, initial: Decimal, args: argparse.Namespace):
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory(prefix="rapana-maker-eval-") as tmp:
        tmp_path = Path(tmp)
        taker_fleet, taker_runner, _ = _build_paper_fleet(
            settings,
            initial=initial,
            ledger_path=tmp_path / "taker.jsonl",
            state_path=tmp_path / "taker-state.json",
            notifier=NullNotifier(),
            allow_live_feeds=False,
        )
        maker_fleet, maker_runner, _ = _build_paper_fleet(
            settings,
            initial=initial,
            ledger_path=tmp_path / "maker.jsonl",
            state_path=tmp_path / "maker-state.json",
            notifier=NullNotifier(),
            allow_live_feeds=False,
        )
        taker_summary = taker_runner.run_replay(
            ReplayProvider(data),
            bars_per_day=args.bars_per_day,
            warmup=args.warmup,
        )
        model = PaperMakerFillModel(
            offset_bps=Decimal(str(settings.paper_maker_offset_bps)),
            lifetime_bars=settings.paper_maker_lifetime_bars,
        )
        maker_summary = maker_runner.run_replay(
            ReplayProvider(data),
            bars_per_day=args.bars_per_day,
            warmup=args.warmup,
            paper_maker_eval=True,
            maker_fill_model=model,
        )
        return summarize_paper_maker_eval(
            taker_summary=taker_summary,
            maker_summary=maker_summary,
            maker_events=maker_fleet.auditor.ledger.read_all(),
            taker_fee_pct=getattr(taker_fleet.trader.executor, "fee_pct", Decimal("0.001")),
            maker_fee_pct=Decimal(str(settings.maker_fee_pct)),
            offset_bps=Decimal(str(settings.paper_maker_offset_bps)),
            lifetime_bars=settings.paper_maker_lifetime_bars,
        )


def _cmd_paper_run(args: argparse.Namespace) -> int:
    """Run the paper-trading daemon on a schedule."""
    configure_logging()
    settings = get_settings()
    mode = getattr(args, "universe", None) or settings.universe_mode
    scout = _build_scout(settings, top_n=getattr(args, "top", None)) if mode == "auto" else None
    fleet, runner, store = _build_paper_fleet(settings, scout=scout, universe_mode=mode)
    # refresh market data each cycle via ingest
    ingester = MarketDataIngester(store=store, settings=settings)
    runner.load_state()
    # Pre-warm cycle-1 data for the auto universe so the first rebalance has prices.
    if scout is not None:
        try:
            picks = scout.select_symbols()
            if picks:
                fleet.symbols = picks
                MarketDataIngester(client=MexcClient(settings=settings), store=store,
                                   settings=settings).ingest_all(symbols=picks)
                print(f"scout selected: {', '.join(picks)}")
        except Exception as exc:
            log.warning("scout_prewarm_failed", error=str(exc))
    print(f"paper-run: interval={settings.paper_interval}s, digest every={settings.digest_every} cycles")
    if args.once:
        MarketDataIngester(client=MexcClient(settings=settings), store=store,
                           settings=settings).ingest_all(symbols=fleet.symbols)
        state = fleet.run_cycle()
        print(state.digest)
        runner.save_state()
        return 0
    # multi-cycle loop (ingest before each cycle)
    import time

    cycle = 0
    try:
        while args.cycles == 0 or cycle < args.cycles:
            cycle += 1
            ingester.ingest_all(symbols=fleet.symbols)
            state = fleet.run_cycle()
            runner.performance.record(cycle, state.equity, fleet.paper.realized_pnl)
            runner.save_state()
            if cycle % settings.digest_every == 0:
                runner.notifier.send("RAPANA digest", state.digest, tags=["robot"])
            time.sleep(settings.paper_interval)
    except KeyboardInterrupt:
        print("\ninterrupted; state saved")
        runner.save_state()
    return 0


def _cmd_notify_test(args: argparse.Namespace) -> int:
    """Send a test notification through the configured sinks."""
    configure_logging()
    settings = get_settings()
    notifier = build_notifier(settings)
    ok = notifier.send("RAPANA test", "notification wiring OK", tags=["white_check_mark"])
    print("notification sent" if ok else "notification FAILED")
    return 0 if ok else 1


def _load_stage_index(settings) -> int:
    import json

    path = settings.state_path
    if not path.exists():
        return 0
    try:
        with open(path, encoding="utf-8") as f:
            return int(json.load(f).get("capital", {}).get("stage_index", 0))
    except Exception:
        return 0


def _save_stage_index(settings, index: int) -> None:
    import json

    path = settings.state_path
    payload = {}
    if path.exists():
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
    payload.setdefault("capital", {})["stage_index"] = index
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _cmd_live_check(args: argparse.Namespace) -> int:
    """Run the live preflight safety gate (does NOT place any order)."""
    configure_logging()
    settings = get_settings()
    capital = StagedCapital(paper=False)
    capital.stage_index = _load_stage_index(settings)
    ks = KillSwitch(settings=settings)
    import rapana.mexc as mexc_pkg

    has_key = bool(mexc_pkg.get_keys().get("apiKey")) if _has_mexc_key_env() else False
    result = preflight(settings, capital, ks, has_api_key=has_key)
    print(result.render())
    return 0 if result.ok else 1


def _has_mexc_key_env() -> bool:
    import os

    return bool(os.environ.get("MEXC_API_KEY"))


def _cmd_promote(args: argparse.Namespace) -> int:
    """Human-approved advance to the next live-capital stage (1%->5%->25%->100%)."""
    configure_logging()
    settings = get_settings()
    capital = StagedCapital(paper=False)
    capital.stage_index = _load_stage_index(settings)
    old = capital.fraction
    capital.advance()
    _save_stage_index(settings, capital.stage_index)
    print(f"capital stage: {old:.0%} -> {capital.fraction:.0%} (stage {capital.stage_index})")
    if settings.ntfy_topic:
        build_notifier(settings).send(
            "RAPANA capital promoted",
            f"deployable capital {old:.0%} -> {capital.fraction:.0%}",
            tags=["chart_with_upwards_trend"],
        )
    return 0


def _cmd_demote(args: argparse.Namespace) -> int:
    """Reset live-capital stage to the minimum (emergency de-risk)."""
    configure_logging()
    settings = get_settings()
    _save_stage_index(settings, 0)
    capital = StagedCapital(paper=False)
    print(f"capital stage RESET to {capital.fraction:.0%}")
    if settings.ntfy_topic:
        build_notifier(settings).send(
            "RAPANA capital demoted", "stage reset to minimum", tags=["warning"]
        )
    return 0


def _cmd_evolve(args: argparse.Namespace) -> int:
    """Self-evolving research loop: catalog → evaluate → mutate near-misses → resume."""
    from pathlib import Path

    from rapana.research.evolve import EvolveConfig, EvolveLoop
    from rapana.research.evolve.state import StateStore

    configure_logging()
    state_dir = Path(args.state_dir)

    if args.status:
        store = StateStore(state_dir)
        st = store.load()
        if st is None:
            print(f"no evolve state at {state_dir}")
            return 1
        print(f"run_id     : {st.run_id}")
        print(f"status     : {st.status}")
        print(f"trials     : {st.global_trial_count}/{st.max_trials}")
        print(f"queue      : {len(st.queue)}")
        print(f"completed  : {len(st.completed)}")
        print(f"edge       : {st.edge_trial_id or '(none)'}")
        if st.notes:
            print("notes:")
            for n in st.notes[-8:]:
                print(f"  - {n}")
        # Best so far
        best = None
        for t in st.trials.values():
            if t.status in ("failed", "passed_wf", "edge", "passed_wf"):
                if best is None or t.dsr > best.dsr:
                    best = t
        if best:
            print(
                f"best so far: {best.trial_id} dsr={best.dsr:.3f} "
                f"oos={best.oos_return:.2%} status={best.status}"
            )
        if store.edge_path.exists():
            print(f"EDGE file  : {store.edge_path}")
        return 0 if st.status != "error" else 1

    cfg = EvolveConfig(
        state_dir=state_dir,
        max_trials=int(args.max_trials),
        stop_on_edge=True,
    )
    loop = EvolveLoop(cfg)
    max_steps = int(args.max_steps) or None
    print("=" * 60)
    print("RAPANA EVOLVE — honest self-evolving research loop")
    print("  gates: DSR≥0.95 + beat benchmark + locked holdout")
    print("  NOT infinite p-hacking — pre-registered catalog + budget")
    print(f"  state: {state_dir}")
    print(f"  max_trials: {cfg.max_trials}")
    print("=" * 60)

    summary = loop.run(resume=not args.fresh, max_steps=max_steps)
    print()
    print("=" * 60)
    print(f"DONE status={summary.status}")
    print(f"  trials_run     : {summary.trials_run}")
    print(f"  best_hypothesis: {summary.best_hypothesis}")
    print(f"  best_dsr       : {summary.best_dsr:.3f}")
    print(f"  edge_trial_id  : {summary.edge_trial_id or '(none)'}")
    if summary.status == "edge_found":
        print("  ★ Edge claim written to state/evolve/EDGE_FOUND.json")
        print("  Still paper-only until human promotes live capital.")
    elif summary.status == "exhausted":
        print("  No tradeable edge in the registered search space.")
        print("  Next restart needs a new surface (L2 / paid data / etc.).")
    print("=" * 60)
    return 0 if summary.status in ("edge_found", "exhausted", "running") else 1


def build_parser() -> argparse.ArgumentParser:
    settings = get_settings()
    parser = argparse.ArgumentParser(prog="rapana", description="Rapana MEXC trading fleet")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="connectivity + config + balances").set_defaults(func=_cmd_status)

    p_ingest = sub.add_parser("ingest", help="pull OHLCV for watched symbols (paginated history)")
    p_ingest.add_argument("--limit", type=int, default=500, help="candles per request page")
    p_ingest.add_argument("--timeframe", default="1h")
    p_ingest.add_argument("--days", type=int, default=0,
                          help="paginate this many days of history (0 = resume from newest stored)")
    p_ingest.add_argument("--max-pages", type=int, default=None, help="cap pagination pages (safety)")
    p_ingest.add_argument("--universe", choices=["fixed", "auto"], default=None,
                          help="auto = ingest the Scout-selected universe instead of watched")
    p_ingest.add_argument("--top", type=int, default=None, help="auto: number of pairs to select")
    p_ingest.set_defaults(func=_cmd_ingest)

    p_if = sub.add_parser(
        "ingest-funding", help="pull perpetual funding-rate history (carry track; no key needed)"
    )
    p_if.add_argument("--limit", type=int, default=200, help="funding rows per request page")
    p_if.add_argument("--timeframe", default="1h", help="timeframe used only for --universe auto scouting")
    p_if.add_argument("--days", type=int, default=0,
                      help="paginate this many days of history (0 = resume from newest stored)")
    p_if.add_argument("--max-pages", type=int, default=None, help="cap pagination pages (safety)")
    p_if.add_argument("--universe", choices=["fixed", "auto"], default=None,
                      help="auto = ingest funding for the Scout-selected universe instead of watched")
    p_if.add_argument("--top", type=int, default=None, help="auto: number of pairs to select")
    p_if.set_defaults(func=_cmd_ingest_funding)

    p_fg = sub.add_parser(
        "ingest-feargreed",
        help="pull full daily Crypto Fear & Greed history (free, no key) into the store",
    )
    p_fg.set_defaults(func=_cmd_ingest_feargreed)

    p_scout = sub.add_parser("scout", help="print the deterministic auto-selected trading universe")
    p_scout.add_argument("--top", type=int, default=None, help="number of pairs to select")
    p_scout.add_argument("--timeframe", default="1h")
    p_scout.set_defaults(func=_cmd_scout)

    sub.add_parser("journal-verify", help="verify the decision journal hash chain").set_defaults(
        func=_cmd_journal_verify
    )

    p_bt = sub.add_parser("backtest", help="backtest a strategy on MEXC history")
    p_bt.add_argument("--symbol", required=True)
    p_bt.add_argument("--strategy", required=True, choices=list(_STRATEGIES))
    p_bt.add_argument("--timeframe", default="1h")
    p_bt.add_argument("--limit", type=int, default=500, help="bars to fetch live (ignored with --from-store)")
    p_bt.add_argument("--from-store", action="store_true",
                      help="backtest on ingested history from the local store (run `ingest` first)")
    p_bt.add_argument("--days", type=int, default=0, help="with --from-store: limit to the last N days")
    p_bt.set_defaults(func=_cmd_backtest)

    p_val = sub.add_parser(
        "validate",
        help="walk-forward out-of-sample validation + Deflated Sharpe (run `ingest` first)",
    )
    p_val.add_argument("--timeframe", default="1h")
    p_val.add_argument("--splits", type=int, default=6, help="number of walk-forward OOS folds")
    p_val.add_argument("--warmup", type=int, default=60, help="lookback bars before each fold")
    p_val.add_argument("--symbol", default=None, help="validate one symbol (default: all watched)")
    p_val.add_argument("--strategy", default=None, choices=list(_STRATEGIES),
                       help="validate one strategy (default: all)")
    p_val.add_argument("--days", type=int, default=0, help="limit to the last N days of stored history")
    p_val.add_argument("--max-weight", type=float, default=0.10,
                       help="fraction of equity per position (fleet-like default 0.10)")
    p_val.add_argument("--holdout", type=float, default=0.0,
                       help="reserve this final fraction as a locked holdout, evaluated once")
    p_val.add_argument("--vol-target", type=float, default=None,
                       help="annualized volatility target for sizing (e.g. 0.5); off by default")
    p_val.set_defaults(func=_cmd_validate)

    p_xs = sub.add_parser(
        "validate-xs",
        help="cross-sectional relative-strength rotation + Deflated Sharpe vs equal-weight HODL",
    )
    p_xs.add_argument("--timeframe", default="1h")
    p_xs.add_argument("--splits", type=int, default=6, help="number of walk-forward OOS folds")
    p_xs.add_argument("--warmup", type=int, default=240, help="lookback bars before each fold")
    p_xs.add_argument("--days", type=int, default=0, help="limit to the last N days of stored history")
    p_xs.add_argument("--signals", default="momentum,reversion",
                      help="comma-separated: momentum,reversion,funding_rank")
    p_xs.add_argument("--lookbacks", default="24,72,168",
                      help="comma-separated trailing-return lookbacks")
    p_xs.add_argument("--top-ks", default="1,3,5", help="comma-separated top-k basket sizes")
    p_xs.add_argument("--rebalances", default="24", help="comma-separated rebalance intervals")
    p_xs.add_argument("--max-weight", type=float, default=0.95,
                      help="max fraction of equity per selected symbol")
    p_xs.add_argument("--fee", type=float, default=0.001,
                      help="taker fee charged on turnover (default 10bp)")
    p_xs.set_defaults(func=_cmd_validate_xs)

    p_vc = sub.add_parser(
        "validate-carry",
        help="funding-rate carry walk-forward + Deflated Sharpe vs CASH (run `ingest-funding` first)",
    )
    p_vc.add_argument("--splits", type=int, default=6, help="number of walk-forward OOS folds")
    p_vc.add_argument("--warmup", type=int, default=8, help="lookback intervals before each fold")
    p_vc.add_argument("--symbol", default=None, help="validate one symbol (default: all stored)")
    p_vc.add_argument("--days", type=int, default=0, help="limit to the last N days of stored funding")
    p_vc.add_argument("--fee", type=float, default=0.0002, help="taker fee per leg (default 2bp)")
    p_vc.add_argument("--slippage", type=float, default=0.0002, help="slippage per leg (default 2bp)")
    p_vc.add_argument("--basis-drag-bps", type=float, default=0.0,
                      help="per-interval residual hedge drag in bps (default 0)")
    p_vc.add_argument("--cash-return", type=float, default=settings.benchmark_cash_return,
                      help="benchmark return to beat (default: RAPANA_BENCHMARK_CASH_RETURN; "
                           "pass 0 for pure cash)")
    p_vc.set_defaults(func=_cmd_validate_carry)

    p_fs = sub.add_parser(
        "validate-funding-spike",
        help="funding-spike reversion event study + Deflated Sharpe vs CASH "
             "(run `ingest-funding` and `ingest` first)",
    )
    p_fs.add_argument("--splits", type=int, default=6, help="number of walk-forward OOS folds")
    p_fs.add_argument("--warmup", type=int, default=8, help="lookback intervals before each fold")
    p_fs.add_argument("--symbol", default=None, help="validate one symbol (default: all stored)")
    p_fs.add_argument("--timeframe", default="1h", help="candle timeframe to join to funding")
    p_fs.add_argument("--days", type=int, default=0, help="limit to the last N days of stored funding")
    p_fs.add_argument("--fee", type=float, default=0.0002, help="taker fee per side (default 2bp)")
    p_fs.add_argument("--slippage", type=float, default=0.0002, help="slippage per side (default 2bp)")
    p_fs.add_argument("--cash-return", type=float, default=settings.benchmark_cash_return,
                      help="benchmark return to beat (default: RAPANA_BENCHMARK_CASH_RETURN; "
                           "pass 0 for pure cash)")
    p_fs.set_defaults(func=_cmd_validate_funding_spike)

    p_vu = sub.add_parser(
        "validate-universe",
        help="point-in-time Scout-vs-majors walk-forward + Deflated Sharpe (run `ingest --universe auto` first)",
    )
    p_vu.add_argument("--timeframe", default="1h")
    p_vu.add_argument("--splits", type=int, default=6, help="number of walk-forward OOS folds")
    p_vu.add_argument("--warmup", type=int, default=60, help="lookback bars before each fold")
    p_vu.add_argument("--top", type=int, default=None, help="universe size (default from settings)")
    p_vu.add_argument("--strategy", default="trend", choices=list(_STRATEGIES),
                      help="strategy applied to each selected symbol")
    p_vu.add_argument("--days", type=int, default=0, help="limit to the last N days of stored history")
    p_vu.add_argument("--max-weight", type=float, default=0.10,
                      help="fraction of equity per position (fleet-like default 0.10)")
    p_vu.add_argument("--vol-target", type=float, default=None,
                      help="annualized volatility target for sizing (e.g. 0.5); off by default")
    p_vu.set_defaults(func=_cmd_validate_universe)

    p_hunt = sub.add_parser(
        "hunt",
        help="alpha hunt: test every event trigger over stored OHLCV + rank by Deflated Sharpe",
    )
    p_hunt.add_argument("--timeframe", default="1h")
    p_hunt.add_argument("--splits", type=int, default=6, help="number of walk-forward OOS folds")
    p_hunt.add_argument("--warmup", type=int, default=24, help="lookback bars before each fold")
    p_hunt.add_argument("--symbol", default=None, help="hunt one symbol (default: all watched)")
    p_hunt.add_argument("--days", type=int, default=0, help="limit to the last N days of stored history")
    p_hunt.add_argument("--fee", type=float, default=0.0002, help="taker fee per side (default 2bp)")
    p_hunt.add_argument("--slippage", type=float, default=0.0002, help="slippage per side (default 2bp)")
    p_hunt.add_argument("--min-events", type=int, default=8, help="min OOS events to score a trigger")
    p_hunt.add_argument("--dsr", type=float, default=0.95, help="Deflated Sharpe threshold to 'pass'")
    p_hunt.add_argument(
        "--pooled",
        action="store_true",
        help="pool each trigger's OOS events across all symbols into ONE trial (highest-power "
             "test of a cross-sectional effect)",
    )
    p_hunt.set_defaults(func=_cmd_hunt)

    p_hf = sub.add_parser(
        "hunt-funding",
        help="alpha hunt on the perp funding grid: test funding event triggers (run `ingest-funding` first)",
    )
    p_hf.add_argument("--timeframe", default="1h", help="candle timeframe to join funding to")
    p_hf.add_argument("--splits", type=int, default=6, help="number of walk-forward OOS folds")
    p_hf.add_argument("--warmup", type=int, default=24, help="lookback intervals before each fold")
    p_hf.add_argument("--fee", type=float, default=0.0002, help="taker fee per side (default 2bp)")
    p_hf.add_argument("--slippage", type=float, default=0.0002, help="slippage per side (default 2bp)")
    p_hf.add_argument("--min-events", type=int, default=5, help="min OOS events to score a trigger")
    p_hf.add_argument("--dsr", type=float, default=0.95, help="Deflated Sharpe threshold to 'pass'")
    p_hf.add_argument("--pooled", action="store_true", help="pool each trigger's OOS events across perps")
    p_hf.set_defaults(func=_cmd_hunt_funding)

    p_conf = sub.add_parser(
        "confirm",
        help="single-hypothesis confirmation of a breakout lead: sweep + locked holdout",
    )
    p_conf.add_argument("--symbol", default="ETH/USDT", help="symbol to confirm")
    p_conf.add_argument("--timeframe", default="1d")
    p_conf.add_argument("--lookbacks", default="15,20,25,30", help="comma list of breakout lookbacks")
    p_conf.add_argument("--horizons", default="8,12,16", help="comma list of hold horizons")
    p_conf.add_argument("--splits", type=int, default=5, help="walk-forward OOS folds")
    p_conf.add_argument("--holdout", type=float, default=0.25, help="locked holdout fraction")
    p_conf.add_argument("--fee", type=float, default=0.0002)
    p_conf.add_argument("--slippage", type=float, default=0.0002)
    p_conf.add_argument("--min-events", type=int, default=8, help="min OOS events to score")
    p_conf.add_argument("--dsr", type=float, default=0.95, help="solo skill DSR threshold to 'confirm'")
    p_conf.set_defaults(func=_cmd_confirm)

    p_run = sub.add_parser("run-fleet", help="run one fleet decision cycle (paper by default)")
    p_run.add_argument("--universe", choices=["fixed", "auto"], default=None,
                       help="auto = Scout-select the universe for this cycle")
    p_run.add_argument("--top", type=int, default=None, help="auto: number of pairs to select")
    p_run.set_defaults(func=_cmd_run_fleet)

    p_replay = sub.add_parser("replay", help="decision backtest: run whole fleet over data (MEXC or synthetic)")
    p_replay.add_argument("--timeframe", default="1h")
    p_replay.add_argument("--limit", type=int, default=1000)
    p_replay.add_argument("--bars-per-day", type=int, default=24)
    p_replay.add_argument("--warmup", type=int, default=60)
    p_replay.add_argument("--equity", type=float, default=10000.0)
    src = p_replay.add_mutually_exclusive_group()
    src.add_argument("--from-store", action="store_true",
                     help="replay over ingested history from the local store (no key needed; run `ingest` first)")
    src.add_argument("--synthetic", action="store_true", help="use synthetic data (no MEXC key needed)")
    p_replay.add_argument("--days", type=int, default=0, help="with --from-store: limit to the last N days")
    p_replay.add_argument("--trace", action="store_true", help="print a sampled decision trace")
    p_replay.add_argument("--trace-every", type=int, default=50, help="bars between trace samples (with --trace)")
    p_replay.add_argument(
        "--maker-eval",
        action="store_true",
        help="run paired taker-vs-maker replay evaluation (paper/replay only; off by default)",
    )
    p_replay.set_defaults(func=_cmd_replay)

    p_paper = sub.add_parser("paper-run", help="run the paper-trading daemon")
    p_paper.add_argument("--cycles", type=int, default=0, help="0 = run forever (Ctrl-C to stop)")
    p_paper.add_argument("--once", action="store_true", help="run a single cycle and exit")
    p_paper.add_argument("--universe", choices=["fixed", "auto"], default=None,
                         help="auto = Scout-select + rebalance the universe each cycle")
    p_paper.add_argument("--top", type=int, default=None, help="auto: number of pairs to select")
    p_paper.set_defaults(func=_cmd_paper_run)

    sub.add_parser("notify-test", help="send a test notification").set_defaults(func=_cmd_notify_test)

    sub.add_parser("live-check", help="run the live preflight safety gate (no order placed)").set_defaults(
        func=_cmd_live_check
    )
    sub.add_parser("promote", help="advance to the next live-capital stage (human gate)").set_defaults(
        func=_cmd_promote
    )
    sub.add_parser("demote", help="reset live-capital stage to minimum (emergency de-risk)").set_defaults(
        func=_cmd_demote
    )

    p_chk = sub.add_parser("check-trade", help="dry-run a trade through the risk gate")
    p_chk.add_argument("--symbol", required=True)
    p_chk.add_argument("--side", required=True, choices=["buy", "sell"])
    p_chk.add_argument("--qty", required=True, type=float)
    p_chk.add_argument("--price", required=True, type=float)
    p_chk.add_argument("--reference", required=True, type=float, help="reference/mid price")
    p_chk.add_argument("--equity", required=True, type=float, help="total account equity (USDT)")
    p_chk.set_defaults(func=_cmd_check_trade)

    p_evolve = sub.add_parser(
        "evolve",
        help="self-evolving research loop: pre-registered catalog + DSR gates until edge or budget",
    )
    p_evolve.add_argument(
        "--state-dir",
        default="./state/evolve",
        help="directory for crash-recoverable state (default: ./state/evolve)",
    )
    p_evolve.add_argument(
        "--max-trials",
        type=int,
        default=200,
        help="hard budget of scored trials (default 200)",
    )
    p_evolve.add_argument(
        "--max-steps",
        type=int,
        default=0,
        help="stop after N trials this session (0 = run until edge or budget)",
    )
    p_evolve.add_argument(
        "--fresh",
        action="store_true",
        help="ignore existing state and start a new run",
    )
    p_evolve.add_argument(
        "--status",
        action="store_true",
        help="print current evolve state and exit (no trials)",
    )
    p_evolve.set_defaults(func=_cmd_evolve)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

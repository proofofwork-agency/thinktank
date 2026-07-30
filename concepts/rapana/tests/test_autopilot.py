from __future__ import annotations

from decimal import Decimal

from rapana.fleet.autopilot import Autopilot, AutopilotPolicy
from rapana.fleet.capital import StagedCapital
from rapana.fleet.performance import PerformanceTracker


def _tracker(equities, initial=10000, benchmark_cash_return=0.0, ts_step=0):
    t = PerformanceTracker(
        initial_equity=Decimal(str(initial)),
        benchmark_cash_return=benchmark_cash_return,
    )
    for i, e in enumerate(equities):
        t.record(i, Decimal(str(e)), Decimal("0"), ts=i * ts_step)
    return t


def _tracker_from_returns(returns, initial=10000, benchmark_cash_return=0.035, ts_step=0):
    equities = [float(initial)]
    for r in returns:
        equities.append(equities[-1] * (1.0 + r))
    return _tracker(
        equities,
        initial=initial,
        benchmark_cash_return=benchmark_cash_return,
        ts_step=ts_step,
    )


def test_disabled_policy_never_acts():
    cap = StagedCapital(paper=False)
    ap = Autopilot(AutopilotPolicy(enabled=False), cap, _tracker([10000, 12000, 9000]))
    assert ap.evaluate() == "hold"
    assert ap.step() == "hold"
    assert cap.fraction == 0.01


def test_demote_on_drawdown_breach():
    cap = StagedCapital(paper=False)
    cap.advance()  # 5%
    policy = AutopilotPolicy(enabled=True, demote_drawdown=0.05)
    # peak 12000 -> 11000 = 8.3% drawdown > 5%
    ap = Autopilot(policy, cap, _tracker([10000, 12000, 11000]))
    assert ap.evaluate() == "demote"
    ap.step()
    assert cap.stage_index == 0  # reset


def test_promote_on_good_performance():
    cap = StagedCapital(paper=False)
    policy = AutopilotPolicy(
        enabled=True, promote_sharpe=0.5, promote_min_cycles=5,
        promote_max_drawdown=0.20, demote_drawdown=0.30, halt_drawdown=1.0,
    )
    # steady uptrend -> positive sharpe, low drawdown, >5 cycles
    equities = [10000 * (1.01 ** i) for i in range(10)]
    ap = Autopilot(policy, cap, _tracker(equities))
    assert ap.evaluate() == "promote"
    before = cap.fraction
    ap.step()
    assert cap.fraction > before


def test_noisy_small_sample_old_sharpe_passes_but_psr_blocks_promotion():
    cap = StagedCapital(paper=False)
    policy = AutopilotPolicy(
        enabled=True,
        promote_min_cycles=5,
        promote_max_drawdown=0.50,
        demote_drawdown=0.50,
        halt_drawdown=1.0,
    )
    ap = Autopilot(
        policy,
        cap,
        _tracker_from_returns([0.4, -0.05, 0.4, 0.1]),
    )
    assert ap._sharpe() > 1.0  # the old naive gate would have promoted
    assert ap._promotion_psr() < policy.promote_psr
    assert ap.evaluate() == "hold"


def test_promotion_requires_return_above_cash_benchmark():
    cap = StagedCapital(paper=False)
    policy = AutopilotPolicy(enabled=True)
    ap = Autopilot(
        policy,
        cap,
        _tracker_from_returns([0.00001] * 600, benchmark_cash_return=0.035),
    )
    assert ap._promotion_psr() > policy.promote_psr
    assert 0 < ap._annualized_return() < ap.performance.benchmark_cash_return
    assert ap.evaluate() == "hold"


def test_hold_when_not_enough_cycles():
    cap = StagedCapital(paper=False)
    policy = AutopilotPolicy(enabled=True)
    ap = Autopilot(policy, cap, _tracker_from_returns([0.001] * 100))
    assert ap.evaluate() == "hold"


def test_promote_on_statistically_and_economically_strong_performance():
    cap = StagedCapital(paper=False)
    policy = AutopilotPolicy(enabled=True)
    ap = Autopilot(
        policy,
        cap,
        _tracker_from_returns([0.001] * 600, benchmark_cash_return=0.035),
    )
    assert ap._promotion_psr() > policy.promote_psr
    assert ap._annualized_return() > ap.performance.benchmark_cash_return
    assert ap.evaluate() == "promote"


def test_halt_trips_kill_switch(tmp_path):
    from rapana.risk.guardrails import KillSwitch

    cap = StagedCapital(paper=False)
    ks = KillSwitch(path=tmp_path / "KS")
    policy = AutopilotPolicy(enabled=True, demote_drawdown=0.5, halt_drawdown=0.20)
    # peak 10000 -> 7000 = 30% drawdown >= 20% halt
    ap = Autopilot(policy, cap, _tracker([8000, 10000, 7000]), kill_switch=ks)
    assert ap.evaluate() == "halt"
    ap.step()
    assert ks.is_tripped() is True


class _SpyNotifier:
    """Counts notifier.send calls so we can assert edge-triggered alerts."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def send(self, *args, **kwargs) -> None:
        self.calls.append((args, kwargs))


def test_recovered_drawdown_does_not_demote():
    cap = StagedCapital(paper=False)
    cap.advance()  # stage 1 (5%)
    policy = AutopilotPolicy(enabled=True, demote_drawdown=0.05, promote_min_cycles=100)
    # Dipped 12000->11000 (historical max dd 8.3%) but recovered to a NEW HIGH
    # 13000: current drawdown is 0, so the reactive demote must NOT fire.
    ap = Autopilot(policy, cap, _tracker([10000, 12000, 11000, 13000]))
    assert ap.evaluate() == "hold"
    ap.step()
    assert cap.stage_index == 1  # capital was NOT reset


def test_demote_is_edge_triggered_no_realert():
    cap = StagedCapital(paper=False)
    cap.advance()
    cap.advance()  # stage 2
    spy = _SpyNotifier()
    policy = AutopilotPolicy(enabled=True, demote_drawdown=0.05, promote_min_cycles=100)
    # Sustained drawdown (trough is the last bar): current dd stays >= demote.
    ap = Autopilot(policy, cap, _tracker([10000, 12000, 11000]), notifier=spy)
    assert ap.step() == "demote"
    assert cap.stage_index == 0
    assert len(spy.calls) == 1  # one de-risk alert on the transition
    # Next cycle still breaching but already at the floor -> no-op, no new alert.
    assert ap.step() == "demote"
    assert cap.stage_index == 0
    assert len(spy.calls) == 1


def test_halt_is_edge_triggered_no_realert(tmp_path):
    from rapana.risk.guardrails import KillSwitch

    cap = StagedCapital(paper=False)
    ks = KillSwitch(path=tmp_path / "KS")
    spy = _SpyNotifier()
    policy = AutopilotPolicy(enabled=True, demote_drawdown=0.5, halt_drawdown=0.20)
    ap = Autopilot(policy, cap, _tracker([8000, 10000, 7000]), notifier=spy, kill_switch=ks)
    assert ap.step() == "halt"
    assert ks.is_tripped() is True
    assert len(spy.calls) == 1  # alert only on the transition into halt
    # Already tripped next cycle -> no re-trip, no re-alert.
    assert ap.step() == "halt"
    assert len(spy.calls) == 1


def test_halt_drawdown_wired_from_settings():
    from types import SimpleNamespace

    from rapana.config import Settings

    # from_settings must read autopilot_halt_drawdown (previously dropped)...
    s = SimpleNamespace(
        autopilot_enabled=True,
        autopilot_promote_sharpe=1.0,
        autopilot_promote_psr=0.95,
        autopilot_promote_min_cycles=100,
        autopilot_promote_max_drawdown=0.10,
        autopilot_promote_cycles_per_year=365,
        autopilot_demote_drawdown=0.08,
        autopilot_halt_drawdown=0.33,
    )
    policy = AutopilotPolicy.from_settings(s)
    assert policy.halt_drawdown == 0.33
    # ...and the Settings field exists with the documented default.
    assert "autopilot_halt_drawdown" in Settings.model_fields
    assert Settings.model_fields["autopilot_halt_drawdown"].default == 0.20
    assert Settings.model_fields["autopilot_promote_min_cycles"].default == 500
    assert Settings.model_fields["autopilot_promote_psr"].default == 0.95


def test_sharpe_bounded_on_zero_variance_series():
    cap = StagedCapital(paper=False)
    # Perfectly smooth +1%/cycle -> variance ~ 0. The std floor must keep Sharpe
    # finite/bounded; the old `sqrt(var) or 1e-9` produced ~1e14 here.
    equities = [10000 * (1.01**i) for i in range(10)]
    ap = Autopilot(AutopilotPolicy(enabled=True), cap, _tracker(equities))
    s = ap._sharpe()
    assert s > 0.0
    assert s < 5000.0  # regression guard against the zero-variance blow-up


def test_paper_demote_resets_stage_and_reports_transition():
    # Manual-inconsistent-state corner: paper mode with an advanced stage. Paper
    # fraction is always 1.0, so the alert must report the STAGE transition, not
    # a misleading "100% -> 100%".
    cap = StagedCapital(paper=True)
    cap.advance()
    cap.advance()  # stage 2 (paper fraction stays 1.0)
    assert cap.stage_index == 2
    spy = _SpyNotifier()
    policy = AutopilotPolicy(enabled=True, demote_drawdown=0.05, promote_min_cycles=100)
    ap = Autopilot(policy, cap, _tracker([10000, 12000, 11000]), notifier=spy)
    assert ap.step() == "demote"
    assert cap.stage_index == 0  # ladder reset even in paper mode
    assert len(spy.calls) == 1
    body = spy.calls[0][0][1]  # send(title, body, tags=...) -> positional body
    assert "stage 2->0" in body

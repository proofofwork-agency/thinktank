from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

from rapana.config import Settings
from rapana.fleet.capital import StagedCapital
from rapana.fleet.execution import Executor, LiveExecutor, OrderResult
from rapana.logging import get_logger
from rapana.risk.guardrails import KillSwitch, TradeProposal

log = get_logger(__name__)

OrderReconcileClass = Literal["expected-filled", "expected-open", "orphan/unknown"]

_CLIENT_ORDER_ID_RE = re.compile(
    r"^rpn-(?P<symbol_hint>[0-9a-zA-Z_-]{1,10})-(?P<digest>[0-9a-f]{16})$"
)
_CLIENT_ORDER_ID_SAFE_RE = re.compile(r"^[0-9a-zA-Z_-]{1,32}$")
_SYMBOL_HINT_RE = re.compile(r"[^0-9a-zA-Z_-]+")


@dataclass(frozen=True)
class ClientOrderIdParts:
    raw: str
    symbol_hint: str
    digest: str


@dataclass(frozen=True)
class OrderReconcileRecord:
    classification: OrderReconcileClass
    client_order_id: str | None
    order_id: str | None
    symbol: str | None
    status: str
    parsed: ClientOrderIdParts | None = None


@dataclass(frozen=True)
class LiveReconcileReport:
    balances: dict[str, Decimal]
    orders: list[OrderReconcileRecord] = field(default_factory=list)


def _deterministic_order_id(proposal: TradeProposal, *, cycle_key: str) -> str:
    """Stable id digest for one logical order inside an explicit cycle stamp.

    The cycle key is required. A content-only id would collide across cycles
    when a legitimate re-entry produces the same symbol/side/qty/price, so the
    caller must provide a replay-deterministic stamp such as
    ``cy{cycle}-ts{bar_ts}``.
    """
    if not cycle_key:
        raise ValueError("cycle_key is required for a deterministic client order id")
    raw = f"{cycle_key}|{proposal.symbol}|{proposal.side}|{proposal.qty}|{proposal.price}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return digest


def _symbol_hint(symbol: str) -> str:
    hint = _SYMBOL_HINT_RE.sub("", symbol)[:10]
    return hint or "sym"


def build_client_order_id(proposal: TradeProposal, *, cycle: int, decision_ts: int) -> str:
    """Build the replay-deterministic id sent to MEXC as ``clientOrderId``.

    MEXC spot accepts only ``[0-9a-zA-Z_-]`` and caps this field at 32
    characters, so the readable portion is a short sanitized symbol hint. The
    16-hex digest carries the full symbol, side, qty, price, cycle, and
    decision timestamp. That keeps ids unique across cycles and stable within a
    cycle without relying on wall-clock time or randomness.
    """
    cycle_key = f"cy{cycle}-ts{decision_ts}"
    digest = _deterministic_order_id(proposal, cycle_key=cycle_key)
    client_order_id = f"rpn-{_symbol_hint(proposal.symbol)}-{digest}"
    if _CLIENT_ORDER_ID_SAFE_RE.fullmatch(client_order_id) is None:
        raise ValueError(f"unsafe client_order_id generated: {client_order_id!r}")
    return client_order_id


def parse_client_order_id(client_order_id: str | None) -> ClientOrderIdParts | None:
    if not client_order_id:
        return None
    match = _CLIENT_ORDER_ID_RE.match(client_order_id)
    if not match:
        return None
    return ClientOrderIdParts(
        raw=client_order_id,
        symbol_hint=match.group("symbol_hint"),
        digest=match.group("digest"),
    )


def _order_client_order_id(order: Mapping) -> str | None:
    for key in ("clientOrderId", "client_order_id", "clientOrderID"):
        raw = order.get(key)
        if raw:
            return str(raw)
    info = order.get("info")
    if isinstance(info, Mapping):
        for key in ("clientOrderId", "client_order_id", "clientOrderID"):
            raw = info.get(key)
            if raw:
                return str(raw)
    return None


def _order_status(order: Mapping) -> str:
    return str(order.get("status") or "").lower()


def _is_filled_order(order: Mapping) -> bool:
    status = _order_status(order)
    if status in {"closed", "filled"}:
        return True
    filled = Decimal(str(order.get("filled") or "0"))
    remaining = Decimal(str(order.get("remaining") or "0"))
    return filled > 0 and remaining <= 0 and status not in {"open", "new", "resting"}


def _is_open_order(order: Mapping) -> bool:
    status = _order_status(order)
    if status in {"open", "new", "resting", "partial", "partially_filled"}:
        return True
    remaining = Decimal(str(order.get("remaining") or "0"))
    return remaining > 0


def classify_reconcile_orders(
    expected_client_order_ids: Iterable[str],
    exchange_orders: Iterable[Mapping],
) -> list[OrderReconcileRecord]:
    """Match exchange orders to intended cycle-stamped ids.

    Classifications:
    - ``expected-filled``: order has an expected client id and the exchange
      reports it filled/closed.
    - ``expected-open``: order has an expected client id and remains open.
    - ``orphan/unknown``: order id is absent/unparseable/unexpected, status is
      unknown, or an expected id is missing from the supplied order set.
    """
    expected = set(expected_client_order_ids)
    seen: set[str] = set()
    records: list[OrderReconcileRecord] = []
    for order in exchange_orders:
        client_order_id = _order_client_order_id(order)
        parsed = parse_client_order_id(client_order_id)
        order_id = str(order.get("id")) if order.get("id") is not None else None
        status = _order_status(order) or "unknown"
        symbol = str(order.get("symbol")) if order.get("symbol") is not None else (
            parsed.symbol_hint if parsed else None
        )
        if client_order_id in expected:
            seen.add(client_order_id)
            if _is_filled_order(order):
                classification: OrderReconcileClass = "expected-filled"
            elif _is_open_order(order):
                classification = "expected-open"
            else:
                classification = "orphan/unknown"
        else:
            classification = "orphan/unknown"
        records.append(OrderReconcileRecord(
            classification=classification,
            client_order_id=client_order_id,
            order_id=order_id,
            symbol=symbol,
            status=status,
            parsed=parsed,
        ))

    for missing in sorted(expected - seen):
        parsed = parse_client_order_id(missing)
        records.append(OrderReconcileRecord(
            classification="orphan/unknown",
            client_order_id=missing,
            order_id=None,
            symbol=(parsed.symbol_hint if parsed else None),
            status="missing",
            parsed=parsed,
        ))
    return records


@dataclass
class PreflightResult:
    ok: bool
    checks: list[tuple[str, bool, str]] = field(default_factory=list)

    @property
    def failures(self) -> list[str]:
        return [name for name, passed, _ in self.checks if not passed]

    def render(self) -> str:
        lines = ["=== LIVE PREFLIGHT ==="]
        for name, passed, detail in self.checks:
            mark = "PASS" if passed else "FAIL"
            lines.append(f"  [{mark}] {name:<22} {detail}")
        lines.append(f"  RESULT: {'OK' if self.ok else 'BLOCKED'}")
        return "\n".join(lines)


def preflight(
    settings: Settings,
    capital: StagedCapital,
    kill_switch: KillSwitch,
    *,
    has_api_key: bool = True,
) -> PreflightResult:
    """Hard safety gate that must pass before ANY live order.

    Checks: env=live, kill switch clear, API key present, capital stage sane,
    withdraw-disabled reminder. This runs in addition to the risk gate and the
    staged-capital cap — defence in depth.
    """
    checks: list[tuple[str, bool, str]] = []
    checks.append(("env_is_live", settings.is_live, f"RAPANA_ENV={settings.env}"))
    checks.append(("kill_switch_clear", not kill_switch.is_tripped(), "fleet must not be halted"))
    checks.append(("api_key_present", has_api_key, "read-only MEXC key required"))
    checks.append((
        "capital_stage_set",
        capital.fraction > 0,
        f"deployable fraction={capital.fraction:.0%}",
    ))
    checks.append((
        "withdraw_disabled_attested",
        bool(getattr(settings, "withdraw_verified", False)),
        "set RAPANA_WITHDRAW_VERIFIED=true AFTER confirming the key has withdraw DISABLED",
    ))
    return PreflightResult(ok=all(p for _, p, _ in checks), checks=checks)


class LiveGuard(Executor):
    """Wraps LiveExecutor with a hard preflight gate + idempotency + reconcile.

    This is the only Executor that should wrap a real MEXC client. It refuses to
    trade unless preflight passes, stamps each order with a client order id
    (so retries don't double-fill), and logs a post-fill balance reconciliation.
    """

    mode = "live"

    def __init__(
        self,
        inner: LiveExecutor,
        settings: Settings,
        capital: StagedCapital,
        kill_switch: KillSwitch,
    ) -> None:
        self.inner = inner
        self.settings = settings
        self.capital = capital
        self.kill_switch = kill_switch
        self._submitted_by_client_order_id: dict[str, OrderResult] = {}
        if self.inner.kill_switch is None:
            self.inner.kill_switch = kill_switch

    def execute(
        self, proposal: TradeProposal, available_cash: Decimal, client_order_id: str | None = None
    ) -> OrderResult:
        result = preflight(
            self.settings, self.capital, self.kill_switch, has_api_key=True,
        )
        if not result.ok:
            log.error("live_preflight_blocked", failures=result.failures)
            self._last_preflight = result
            return OrderResult(
                status="rejected",
                symbol=proposal.symbol,
                side=proposal.side,
                mode=self.mode,
                proposed_qty=proposal.qty,
                filled_qty=Decimal("0"),
                price=proposal.price,
                fee=Decimal("0"),
                client_order_id=client_order_id,
            )

        exchange = self.inner.client.exchange
        result = preflight(
            self.settings, self.capital, self.kill_switch,
            has_api_key=bool(getattr(exchange, "apiKey", None)),
        )
        if not result.ok:
            log.error("live_preflight_blocked", failures=result.failures)
            self._last_preflight = result
            return OrderResult(
                status="rejected",
                symbol=proposal.symbol,
                side=proposal.side,
                mode=self.mode,
                proposed_qty=proposal.qty,
                filled_qty=Decimal("0"),
                price=proposal.price,
                fee=Decimal("0"),
                client_order_id=client_order_id,
            )
        self._last_preflight = result
        if client_order_id is None:
            log.error("live_order_missing_client_order_id", symbol=proposal.symbol)
            return OrderResult(
                status="rejected",
                symbol=proposal.symbol,
                side=proposal.side,
                mode=self.mode,
                proposed_qty=proposal.qty,
                filled_qty=Decimal("0"),
                price=proposal.price,
                fee=Decimal("0"),
                reason="missing_client_order_id",
            )
        if client_order_id in self._submitted_by_client_order_id:
            log.warning(
                "live_order_retry_deduped",
                symbol=proposal.symbol,
                client_order_id=client_order_id,
            )
            return self._submitted_by_client_order_id[client_order_id]
        log.warning("live_order_dispatching", symbol=proposal.symbol, client_order_id=client_order_id)
        result = self.inner.execute(proposal, available_cash, client_order_id=client_order_id)
        if result.submitted:
            self._submitted_by_client_order_id[client_order_id] = result
        return result

    def reconcile(
        self,
        quote: str = "USDT",
        *,
        expected_client_order_ids: Iterable[str] = (),
        exchange_orders: Iterable[Mapping] | None = None,
    ) -> LiveReconcileReport | None:
        """Re-read balances and reconcile exchange orders to intended ids.

        Contract for restart/retry recovery: callers provide the set of intended
        cycle-stamped ``clientOrderId`` values from the journal/state. The live
        order read (currently passed as ``exchange_orders`` while the live path
        stays parked) is matched by client id and classified as
        ``expected-filled``, ``expected-open``, or ``orphan/unknown``. Missing
        expected ids are also returned as ``orphan/unknown`` so a restart cannot
        silently assume a fill or safe absence.

        Returns ``None`` on balance fetch FAILURE (balance UNKNOWN). A successful
        read returns ``LiveReconcileReport`` even if balances/orders are empty.
        Never conflates an outage with "no money": callers MUST treat ``None`` as
        "could not verify", not as zero. ``quote`` is retained for call-site
        compatibility and future exchange filtering.
        """
        _ = quote
        try:
            raw = self.inner.client.fetch_balance()
            total = raw.get("total", {}) or {}
            balances = {k: Decimal(str(v)) for k, v in total.items() if v}
            orders = classify_reconcile_orders(
                expected_client_order_ids,
                exchange_orders or (),
            )
            return LiveReconcileReport(balances=balances, orders=orders)
        except Exception as exc:
            log.error("reconcile_failed", error=str(exc))
            return None

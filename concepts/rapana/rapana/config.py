from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file.

    Secrets (MEXC keys) are loaded via a separate secrets interface (rapana.secrets)
    so the storage backend can be swapped from .env to a vault without touching
    call sites.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        extra="ignore",
    )

    # --- Runtime ---
    env: str = Field(default="paper", alias="RAPANA_ENV")
    log_level: str = Field(default="INFO", alias="RAPANA_LOG_LEVEL")
    kill_switch_path: Path = Field(default=Path("./state/KILL_SWITCH"), alias="RAPANA_KILL_SWITCH_PATH")
    # Human-attested: the MEXC key has withdraw DISABLED. Cannot be verified via
    # API, so this is a fail-CLOSED live gate (default False). Flip to True only
    # after manually confirming the key's permissions in the MEXC dashboard.
    withdraw_verified: bool = Field(default=False, alias="RAPANA_WITHDRAW_VERIFIED")

    # --- Markets ---
    watch_symbols_raw: str = Field(default="BTC/USDT,ETH/USDT,SOL/USDT", alias="RAPANA_WATCH_SYMBOLS")

    # --- Storage ---
    db_path: Path = Field(default=Path("./data/rapana.db"), alias="RAPANA_DB_PATH")
    journal_path: Path = Field(default=Path("./journal/decisions.jsonl"), alias="RAPANA_JOURNAL_PATH")
    state_path: Path = Field(default=Path("./state/fleet.json"), alias="RAPANA_STATE_PATH")
    digest_path: Path = Field(default=Path("./logs/digest.jsonl"), alias="RAPANA_DIGEST_PATH")

    # --- Paper runner ---
    paper_interval: int = Field(default=3600, alias="RAPANA_PAPER_INTERVAL")  # seconds between cycles
    digest_every: int = Field(default=24, alias="RAPANA_DIGEST_EVERY")        # cycles per digest

    # --- Notifications ---
    notify_console: bool = Field(default=True, alias="RAPANA_NOTIFY_CONSOLE")
    ntfy_topic: str | None = Field(default=None, alias="RAPANA_NTFY_TOPIC")
    ntfy_server: str = Field(default="https://ntfy.sh", alias="RAPANA_NTFY_SERVER")

    # --- Autopilot (autonomous capital scaling / de-risking) ---
    autopilot_enabled: bool = Field(default=False, alias="RAPANA_AUTOPILOT")
    autopilot_promote_sharpe: float = Field(default=1.0, alias="RAPANA_AUTOPILOT_PROMOTE_SHARPE")
    autopilot_promote_psr: float = Field(default=0.95, alias="RAPANA_AUTOPILOT_PROMOTE_PSR")
    autopilot_promote_min_cycles: int = Field(default=500, alias="RAPANA_AUTOPILOT_PROMOTE_MIN_CYCLES")
    autopilot_promote_max_drawdown: float = Field(default=0.10, alias="RAPANA_AUTOPILOT_PROMOTE_MAX_DD")
    autopilot_promote_cycles_per_year: int = Field(
        default=365, alias="RAPANA_AUTOPILOT_PROMOTE_CYCLES_PER_YEAR"
    )
    autopilot_demote_drawdown: float = Field(default=0.08, alias="RAPANA_AUTOPILOT_DEMOTE_DD")
    autopilot_halt_drawdown: float = Field(default=0.20, alias="RAPANA_AUTOPILOT_HALT_DD")

    # --- Benchmarking (honest idle-cash opportunity cost) ---
    benchmark_cash_return: float = Field(default=0.035, alias="RAPANA_BENCHMARK_CASH_RETURN")

    # --- Live sizing (vol targeting is opt-in; default preserves existing behavior) ---
    vol_target: float | None = Field(default=None, alias="RAPANA_VOL_TARGET")
    vol_lookback: int = Field(default=20, alias="RAPANA_VOL_LOOKBACK")

    # --- Execution mode (maker is opt-in; market preserves current behavior) ---
    execution_mode: str = Field(default="market", alias="RAPANA_EXECUTION_MODE")
    maker_poll_timeout_sec: float = Field(default=2.0, alias="RAPANA_MAKER_POLL_TIMEOUT_SEC")
    maker_poll_interval_sec: float = Field(default=0.25, alias="RAPANA_MAKER_POLL_INTERVAL_SEC")
    maker_price_peg: str = Field(default="passive_touch", alias="RAPANA_MAKER_PRICE_PEG")
    maker_price_offset_ticks: int = Field(default=0, alias="RAPANA_MAKER_PRICE_OFFSET_TICKS")
    maker_fee_pct: float = Field(default=0.0005, alias="RAPANA_MAKER_FEE_PCT")
    paper_maker_offset_bps: float = Field(default=2.0, alias="RAPANA_PAPER_MAKER_OFFSET_BPS")
    paper_maker_lifetime_bars: int = Field(default=1, alias="RAPANA_PAPER_MAKER_LIFETIME_BARS")
    paper_maker_fill_fraction: float = Field(default=0.0, alias="RAPANA_PAPER_MAKER_FILL_FRACTION")

    # --- Capital budget (hard ceiling on deployable equity; micro accounts) ---
    # When set, risk notional caps are clamped so a single order cannot exceed
    # this budget. Example: RAPANA_CAPITAL_BUDGET_USD=50 for a $50 max bankroll.
    capital_budget_usd: float | None = Field(default=None, alias="RAPANA_CAPITAL_BUDGET_USD")

    # --- Risk policy ---
    risk_max_position_pct: float = Field(default=0.10, alias="RAPANA_RISK_MAX_POSITION_PCT")
    risk_max_total_exposure_pct: float = Field(default=0.50, alias="RAPANA_RISK_MAX_TOTAL_EXPOSURE_PCT")
    risk_max_daily_loss_pct: float = Field(default=0.03, alias="RAPANA_RISK_MAX_DAILY_LOSS_PCT")
    risk_max_orders_per_min: int = Field(default=6, alias="RAPANA_RISK_MAX_ORDERS_PER_MIN")
    risk_max_notional_per_order: float = Field(default=250.0, alias="RAPANA_RISK_MAX_NOTIONAL_PER_ORDER")
    risk_sanity_price_band: float = Field(default=0.05, alias="RAPANA_RISK_SANITY_PRICE_BAND")

    # --- LLM brain (optional; provider=none keeps fleet offline/deterministic) ---
    llm_provider: str = Field(default="none", alias="RAPANA_LLM_PROVIDER")
    llm_base_url: str | None = Field(default=None, alias="RAPANA_LLM_BASE_URL")
    llm_api_key: str | None = Field(default=None, alias="RAPANA_LLM_API_KEY")
    llm_model: str | None = Field(default=None, alias="RAPANA_LLM_MODEL")
    # Add the LLM regime analyst to the FORWARD fleet roster. Only takes effect
    # when a real brain is configured (provider != none) — otherwise it is a
    # no-op neutral vote. Never wired into replay/backtest (lookahead).
    llm_regime_enabled: bool = Field(default=False, alias="RAPANA_LLM_REGIME_ENABLED")

    # --- External alpha feeds (sentiment/macro). OFF by default: live network
    # feeds must never run in replay/backtest (lookahead bias), so historical
    # commands force them off regardless of this flag. Enable for forward
    # paper/live where "now" data is point-in-time correct.
    feeds_enabled: bool = Field(default=False, alias="RAPANA_FEEDS_ENABLED")
    coingecko_api_key: str | None = Field(default=None, alias="RAPANA_COINGECKO_API_KEY")

    # --- Universe / Scout (deterministic pair selection; "fixed" = unchanged) ---
    universe_mode: str = Field(default="fixed", alias="RAPANA_UNIVERSE_MODE")  # fixed | auto
    universe_top_n: int = Field(default=5, alias="RAPANA_UNIVERSE_TOP_N")
    universe_min_quote_volume_usd: float = Field(
        default=2_000_000.0, alias="RAPANA_UNIVERSE_MIN_QUOTE_VOLUME_USD"
    )
    universe_momentum_lookback: int = Field(default=30, alias="RAPANA_UNIVERSE_MOMENTUM_LOOKBACK")
    universe_rebalance_bars: int = Field(default=24, alias="RAPANA_UNIVERSE_REBALANCE_BARS")
    universe_candidate_k: int = Field(default=50, alias="RAPANA_UNIVERSE_CANDIDATE_K")

    @field_validator("env")
    @classmethod
    def _validate_env(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in {"paper", "live"}:
            raise ValueError("RAPANA_ENV must be 'paper' or 'live'")
        return v

    @field_validator("llm_provider")
    @classmethod
    def _validate_llm_provider(cls, v: str) -> str:
        v = v.strip().lower()
        allowed = {"none", "deterministic", "openrouter", "ollama", "openai", "openai-compatible", "local"}
        # Coerce unknown/typo to "none" so a misconfig never crashes the fleet.
        return v if v in allowed else "none"

    @field_validator("vol_target", mode="before")
    @classmethod
    def _empty_vol_target_is_off(cls, v: object) -> object:
        if v == "":
            return None
        return v

    @field_validator("capital_budget_usd", mode="before")
    @classmethod
    def _empty_capital_budget_is_off(cls, v: object) -> object:
        if v == "" or v is None:
            return None
        return v

    @field_validator("capital_budget_usd")
    @classmethod
    def _positive_capital_budget(cls, v: float | None) -> float | None:
        if v is None:
            return None
        if float(v) <= 0:
            raise ValueError("RAPANA_CAPITAL_BUDGET_USD must be positive when set")
        return float(v)

    @field_validator("execution_mode")
    @classmethod
    def _validate_execution_mode(cls, v: str) -> str:
        v = v.strip().lower()
        return v if v in {"market", "maker"} else "market"

    @field_validator("maker_price_peg")
    @classmethod
    def _validate_maker_price_peg(cls, v: str) -> str:
        v = v.strip().lower()
        return v if v == "passive_touch" else "passive_touch"

    @field_validator("paper_maker_fill_fraction")
    @classmethod
    def _clamp_paper_maker_fill_fraction(cls, v: float) -> float:
        return max(0.0, min(1.0, v))

    @field_validator("maker_fee_pct")
    @classmethod
    def _clamp_maker_fee_pct(cls, v: float) -> float:
        return max(0.0, v)

    @field_validator("paper_maker_offset_bps")
    @classmethod
    def _clamp_paper_maker_offset_bps(cls, v: float) -> float:
        return max(0.0, v)

    @field_validator("paper_maker_lifetime_bars")
    @classmethod
    def _clamp_paper_maker_lifetime_bars(cls, v: int) -> int:
        return max(1, v)

    @field_validator("universe_mode")
    @classmethod
    def _validate_universe_mode(cls, v: str) -> str:
        v = v.strip().lower()
        # Coerce unknown/typo to "fixed" so a misconfig never silently flips to auto.
        return v if v in {"fixed", "auto"} else "fixed"

    @property
    def watch_symbols(self) -> list[str]:
        return [s.strip().upper() for s in self.watch_symbols_raw.split(",") if s.strip()]

    @property
    def is_live(self) -> bool:
        return self.env == "live"

    @property
    def effective_max_notional_per_order(self) -> float:
        """Per-order notional cap, clamped by capital budget when set.

        Micro accounts (e.g. $50) must never inherit the $250 default — a single
        order would be 5× the bankroll. When a budget is set we allow at most
        95% of budget in one order (leaves dust for fees).
        """
        cap = float(self.risk_max_notional_per_order)
        if self.capital_budget_usd is not None:
            cap = min(cap, float(self.capital_budget_usd) * 0.95)
        return cap

    @property
    def effective_capital_budget(self) -> float | None:
        return self.capital_budget_usd


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()

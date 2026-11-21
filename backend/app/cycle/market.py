"""Daily market/macro panel used by the cycle engine.

The panel is built from local observations only (macro_obs + market_bars), so
every number the engine later derives is auditable back to a database row and a
vintage date. No network access happens here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import Instrument, MacroObs, MacroSeries, MarketBar
from app.platform.frames import pivot_series_rows


@dataclass
class Panel:
    daily: pd.DataFrame
    first: str | None = None
    last: str | None = None
    columns: list[str] = field(default_factory=list)

    def series(self, code: str) -> pd.Series:
        if code not in self.daily.columns:
            return pd.Series(dtype="float64")
        return self.daily[code].dropna()


def load_panel(session: Session) -> Panel:
    """Load a daily close frame indexed by UTC date."""
    macro_rows = session.execute(
        select(MacroSeries.code, MacroObs.ts_utc, MacroObs.value).join(
            MacroSeries, MacroSeries.id == MacroObs.series_id
        )
    ).all()
    macro = pivot_series_rows(macro_rows, key="code", ts="ts", value="value", aggfunc="last")
    bar_rows = session.execute(
        select(Instrument.symbol, MarketBar.ts_utc, MarketBar.close)
        .join(Instrument, Instrument.id == MarketBar.instrument_id)
        .where(MarketBar.timeframe == "1d")
    ).all()
    bars = pivot_series_rows(bar_rows, key="code", ts="ts", value="value", aggfunc="last")

    daily = pd.DataFrame()
    if not macro.empty:
        daily = macro.ffill(limit=7)
    if not bars.empty:
        close = bars.ffill(limit=5)
        daily = close if daily.empty else daily.join(close, how="outer").sort_index()

    if daily.empty:
        return Panel(daily=pd.DataFrame())
    daily = daily[~daily.index.duplicated(keep="last")]
    return Panel(
        daily=daily,
        first=daily.index.min().strftime("%Y-%m-%d"),
        last=daily.index.max().strftime("%Y-%m-%d"),
        columns=list(daily.columns),
    )


def eval_expression(panel: Panel, expression: str) -> pd.Series:
    """Evaluate an indicator expression against the panel columns.

    Expressions are authored in ``config/cycle.yaml`` (trusted local file) and
    only use column arithmetic plus ``Series.shift``. Column names are replaced
    by safe placeholders first, because some symbols (e.g. ``000300``) are not
    valid Python identifiers. We deliberately avoid ``DataFrame.eval`` because
    the ``shift`` calls need real Series objects.
    """
    columns = list(panel.daily.columns)
    placeholders: dict[str, str] = {}
    pattern = None
    if columns:
        ordered = sorted(columns, key=len, reverse=True)
        for index, column in enumerate(ordered):
            placeholders[column] = f"_c{index}"
        pattern = re.compile("|".join(re.escape(column) for column in ordered))
    text = pattern.sub(lambda match: placeholders[match.group(0)], expression) if pattern else expression
    namespace = {placeholder: panel.daily[column] for column, placeholder in placeholders.items()}
    namespace["__builtins__"] = {}
    try:
        value = eval(text, namespace)  # noqa: S307 - config-authored expression
    except Exception:  # pragma: no cover - defensive: malformed config
        return pd.Series(dtype="float64")
    if isinstance(value, pd.Series):
        return pd.to_numeric(value, errors="coerce")
    if isinstance(value, (int, float)):
        return pd.Series(float(value), index=panel.daily.index)
    return pd.Series(dtype="float64")


def indicator_series(panel: Panel, spec: dict) -> pd.Series:
    expression = str(spec.get("expr") or "").strip()
    if not expression:
        return pd.Series(dtype="float64")
    return eval_expression(panel, expression).reindex(panel.daily.index)


def zscore(series: pd.Series, window_days: int = 2520, min_obs: int = 250, clip: float = 3.5) -> pd.Series:
    clean = pd.to_numeric(series, errors="coerce").astype("float64")
    window = f"{int(window_days)}D"
    mean = clean.rolling(window, min_periods=min_obs).mean()
    std = clean.rolling(window, min_periods=min_obs).std()
    z = (clean - mean) / std.where(std > 0)
    return pd.to_numeric(z, errors="coerce").clip(lower=-clip, upper=clip)

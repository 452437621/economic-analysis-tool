"""Ordered provider chains per data domain.

This registry is deliberately metadata-only: collectors still own parsing and
symbol mappings.  ``failover.run_chain`` executes candidates built from these
source definitions, and the sources API uses the same registry to show
primary/backup roles, health and cooldown state.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingest.failover import breaker_state, chain_stats
from app.ingest.sources import (
    SOURCE_ECB,
    SOURCE_EM,
    SOURCE_FED_RESEARCH,
    SOURCE_FRANKFURTER,
    SOURCE_FRED,
    SOURCE_IMF,
    SOURCE_JGB,
    SOURCE_NYFED,
    SOURCE_SINA,
    SOURCE_TENCENT,
    SOURCE_TREASURY,
    SOURCE_TREASURY_FISCAL,
    SOURCE_WORLDBANK,
)
from app.models.core import Source


@dataclass(frozen=True)
class Chain:
    id: str
    domain: str
    title: str
    sources: tuple[dict, ...]
    action_job: str
    critical: bool = False

    @property
    def single_source(self) -> bool:
        return len(self.sources) == 1


CHAINS: dict[str, Chain] = {
    "quotes.cn_futures": Chain("quotes.cn_futures", "quotes", "国内期货快照", (SOURCE_SINA,), "collect_quotes"),
    "quotes.overseas": Chain(
        "quotes.overseas", "quotes", "外盘/现货快照", (SOURCE_SINA, SOURCE_TENCENT), "collect_quotes"
    ),
    "quotes.fx": Chain(
        "quotes.fx", "quotes", "汇率快照", (SOURCE_SINA, SOURCE_EM, SOURCE_FRANKFURTER), "collect_quotes"
    ),
    "quotes.cn_equity": Chain(
        "quotes.cn_equity", "quotes", "A股/指数快照", (SOURCE_EM, SOURCE_TENCENT), "collect_quotes", critical=True
    ),
    "quotes.us_indices": Chain(
        "quotes.us_indices", "quotes", "美股指数快照", (SOURCE_TENCENT, SOURCE_EM), "collect_quotes", critical=True
    ),
    "quotes.dxy": Chain(
        "quotes.dxy", "quotes", "美元指数快照", (SOURCE_EM, SOURCE_SINA), "collect_quotes", critical=True
    ),
    "bars.cn_futures": Chain("bars.cn_futures", "bars", "国内期货日线", (SOURCE_SINA,), "collect_daily_bars"),
    "bars.overseas": Chain("bars.overseas", "bars", "外盘/现货日线", (SOURCE_SINA,), "collect_daily_bars"),
    "bars.us_indices": Chain(
        "bars.us_indices", "bars", "美股指数日线", (SOURCE_TENCENT, SOURCE_EM), "collect_daily_bars", critical=True
    ),
    "bars.cn_equity": Chain(
        "bars.cn_equity", "bars", "A股/指数日线", (SOURCE_EM, SOURCE_TENCENT), "collect_daily_bars", critical=True
    ),
    "bars.fx": Chain(
        "bars.fx", "bars", "汇率日线", (SOURCE_SINA, SOURCE_EM, SOURCE_FRANKFURTER), "collect_daily_bars"
    ),
    "rates.us_treasury": Chain(
        "rates.us_treasury", "rates", "美国国债收益率", (SOURCE_TREASURY, SOURCE_FRED), "collect_rates", critical=True
    ),
    "rates.money_market": Chain(
        "rates.money_market", "rates", "SOFR/EFFR", (SOURCE_NYFED, SOURCE_FRED), "collect_rates", critical=True
    ),
    "rates.jp": Chain("rates.jp", "rates", "日本国债收益率", (SOURCE_JGB,), "collect_rates"),
    "rates.eu": Chain("rates.eu", "rates", "欧元区国债收益率", (SOURCE_ECB,), "collect_rates"),
    "macro.h41": Chain(
        "macro.h41", "macro", "美联储资产负债表", (SOURCE_FED_RESEARCH, SOURCE_FRED), "collect_macro", critical=True
    ),
    "macro.h6": Chain(
        "macro.h6", "macro", "货币供应 M1/M2", (SOURCE_FED_RESEARCH, SOURCE_FRED), "collect_macro", critical=True
    ),
    "macro.annual.imf": Chain(
        "macro.annual.imf", "macro", "年频结构性宏观", (SOURCE_IMF, SOURCE_WORLDBANK), "collect_macro"
    ),
    "macro.fiscal": Chain(
        "macro.fiscal", "macro", "美国财政收支/债务", (SOURCE_TREASURY_FISCAL, SOURCE_FRED), "collect_macro"
    ),
    "gold.price": Chain("gold.price", "gold", "黄金价格", (SOURCE_SINA,), "collect_gold"),
}


def chains_for_source(source_name: str) -> list[str]:
    return [chain.id for chain in CHAINS.values() if any(src["name"] == source_name for src in chain.sources)]


def source_roles() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for chain in CHAINS.values():
        for index, src in enumerate(chain.sources):
            entry = out.setdefault(src["name"], {"roles": set(), "domains": set(), "chains": set()})
            entry["roles"].add("primary" if index == 0 else "backup")
            entry["domains"].add(chain.domain)
            entry["chains"].add(chain.id)
    return {
        name: {
            "roles": sorted(value["roles"]),
            "domains": sorted(value["domains"]),
            "chains": sorted(value["chains"]),
        }
        for name, value in out.items()
    }


def chain_summaries(session: Session, now: datetime | None = None) -> list[dict]:
    current = now or datetime.now(timezone.utc)
    sources = {row.name: row for row in session.scalars(select(Source)).all()}
    out: list[dict] = []
    for chain in CHAINS.values():
        candidates = []
        healthy = 0
        open_count = 0
        unknown_count = 0
        for index, conf in enumerate(chain.sources):
            source = sources.get(conf["name"])
            state = (
                breaker_state(session, source.id, current)
                if source is not None
                else {
                    "success_rate_24h": None,
                    "consecutive_failures": 0,
                    "cooldown_until": None,
                    "open": False,
                    "last_success": None,
                    "checks_24h": 0,
                }
            )
            checked = bool(state.get("checks_24h"))
            if source is not None and not state["open"] and checked:
                healthy += 1
            elif state["open"]:
                open_count += 1
            else:
                unknown_count += 1
            candidates.append(
                {
                    "source": conf["name"],
                    "role": "primary" if index == 0 else "backup",
                    "tier": conf.get("tier"),
                    "reliability": conf.get("reliability"),
                    "healthy": bool(source is not None and checked and not state["open"]),
                    "cooldown_until": state["cooldown_until"].isoformat()
                    if state["cooldown_until"]
                    else None,
                    "consecutive_failures": state["consecutive_failures"],
                    "success_rate_24h": state["success_rate_24h"],
                    "last_success": state["last_success"].isoformat()
                    if state["last_success"]
                    else None,
                }
            )
        if healthy == 0 and unknown_count == len(chain.sources):
            status = "unknown"
        elif healthy == 0:
            status = "down"
        elif open_count or unknown_count or (chain.single_source and candidates[0]["consecutive_failures"]):
            status = "degraded"
        else:
            status = "ok"
        stats = chain_stats(chain.id)
        out.append(
            {
                "id": chain.id,
                "domain": chain.domain,
                "title": chain.title,
                "critical": chain.critical,
                "single_source": chain.single_source,
                "action_job": chain.action_job,
                "status": status,
                "last_used": stats.get("last_used"),
                "last_success": stats.get("last_success"),
                "last_provider": stats.get("last_provider"),
                "candidates": candidates,
            }
        )
    return out

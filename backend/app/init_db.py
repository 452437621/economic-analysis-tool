"""Initialize database schema and seed default instruments/jobs.

Usage:  python -m app.init_db
"""

from __future__ import annotations

import logging

import yaml
from sqlalchemy import select

from app.models.base import utcnow
from app.models.core import Instrument, Job, WatchItem
from app.platform.config import ROOT_DIR, settings
from app.platform.db import SessionLocal, init_db
from app.platform.instrument_units import UNIT_BY_SYMBOL

logger = logging.getLogger(__name__)

# 交易所标准合约参数（近似值，用户应按期货公司实际标准覆写 extra/margin）
CONTRACT_SPECS: dict[str, dict] = {
    "AU": {"contract_size": 1000, "margin_pct": 0.09, "fee_per_lot": 10.0, "tick_size": 0.02},
    "AG": {"contract_size": 15, "margin_pct": 0.10, "fee_per_lot": 3.0, "tick_size": 1.0},
    "CU": {"contract_size": 5, "margin_pct": 0.10, "fee_per_lot": 15.0, "tick_size": 10.0},
    "AL": {"contract_size": 5, "margin_pct": 0.10, "fee_per_lot": 3.0, "tick_size": 5.0},
    "ZN": {"contract_size": 5, "margin_pct": 0.10, "fee_per_lot": 3.0, "tick_size": 5.0},
    "NI": {"contract_size": 1, "margin_pct": 0.12, "fee_per_lot": 3.0, "tick_size": 10.0},
    "SC": {"contract_size": 1000, "margin_pct": 0.12, "fee_per_lot": 20.0, "tick_size": 0.1},
    "M": {"contract_size": 10, "margin_pct": 0.08, "fee_per_lot": 1.5, "tick_size": 1.0},
    "I": {"contract_size": 100, "margin_pct": 0.10, "fee_per_lot": 2.0, "tick_size": 0.5},
    "SR": {"contract_size": 10, "margin_pct": 0.07, "fee_per_lot": 3.0, "tick_size": 1.0},
    "CF": {"contract_size": 5, "margin_pct": 0.07, "fee_per_lot": 4.3, "tick_size": 5.0},
    "P": {"contract_size": 10, "margin_pct": 0.09, "fee_per_lot": 2.5, "tick_size": 2.0},
    "603993": {
        "contract_size": 1,
        "margin_pct": 1.0,
        "fee_per_lot": 0.0,
        "commission_rate": 0.0003,
        "tick_size": 0.01,
    },
}


def seed_instruments() -> int:
    """Seed/update instrument master data from config/default.yaml (idempotent)."""
    config_path = ROOT_DIR / "config" / "default.yaml"
    if not config_path.exists():
        logger.warning("config file not found: %s", config_path)
        return 0

    with config_path.open("r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh) or {}
    groups = (config.get("market") or {}).get("instruments") or {}

    created = 0
    with SessionLocal() as session:
        for asset_class, items in groups.items():
            for item in items:
                symbol = str(item["symbol"])
                exists = session.scalar(
                    select(Instrument).where(Instrument.symbol == symbol)
                )
                if exists is None:
                    exists = Instrument(
                        symbol=symbol,
                        name=str(item.get("name", symbol)),
                        exchange=item.get("exchange"),
                        asset_class=str(item.get("asset_class", asset_class)),
                        currency=item.get("currency"),
                        active=True,
                    )
                    session.add(exists)
                    created += 1
                spec = CONTRACT_SPECS.get(symbol)
                extra = dict(exists.extra or {})
                if spec:
                    exists.contract_size = spec["contract_size"]
                    exists.margin_pct = spec["margin_pct"]
                    extra.update(
                        {key: value for key, value in spec.items() if key not in ("contract_size", "margin_pct")}
                    )
                if symbol in UNIT_BY_SYMBOL:
                    extra["unit"] = UNIT_BY_SYMBOL[symbol]
                if extra:
                    exists.extra = extra
        session.commit()
    logger.info("seeded/updated %s instruments", created)
    return created


JOBS_DEFAULT: dict[str, str] = {
    "heartbeat": "every 60s",
    "collect_quotes": "every 60s",
    "collect_news": "every 3m",
    "collect_news_slow": "08:15",
    "collect_rates": "every 1h",
    "collect_macro": "08:05",
    "collect_calendar": "every 6h",
    "collect_positions": "15:45",
    "collect_gold": "16:40",
    "collect_bodies": "every 10m",
    "collect_daily_bars": "15:40 / 06:30",
    "backfill_history": "周日 09:00",
    "extract_claims": "every 15m",
    "extract_events": "every 30m",
    "extract_claims_llm": "every 20m (需 LLM Key)",
    "check_data_quality": "15:50",
    "analyze": "16:10",
    "cycle": "16:20",
    "lenses": "16:25",
    "decide": "16:30",
    "theses": "16:35",
    "scan_alerts": "every 5m",
    "score_predictions": "17:00",
    "ledger": "16:45",
    "timeline": "周日 09:30",
    "brief_premarket": "07:30",
    "brief_postmarket": "21:00",
    "weekly_review": "周日 10:00",
    "monthly_review": "每月 1 日 10:00",
    "brief_manual": "manual",
}


# 任务说明：系统状态页「任务描述」列直接读这里（随启动刷新，属于代码所有的文案）。
JOB_DESCRIPTIONS: dict[str, str] = {
    "heartbeat": "调度器心跳：每 60 秒确认后台调度进程存活，并记录最近心跳时间。",
    "collect_quotes": "采集全市场最新快照行情（A股/美股/指数、外汇、商品、贵金属），供总览与研判读取实时价。",
    "collect_news": "增量抓取财经新闻与公告索引，为事件抽取和简报提供语料。",
    "collect_news_slow": "每日慢速深抓新闻：补采快讯遗漏的深度文章与更正内容。",
    "collect_rates": "采集利率与流动性数据（美债/德债/日债收益率、SOFR/EFFR 等），每小时更新。",
    "collect_macro": "采集结构性宏观序列（IMF/财政部/世界银行等），每日 08:05 刷新。",
    "collect_calendar": "采集财经日历（议息、CPI、非农等重要事件），每 6 小时刷新未来窗口。",
    "collect_positions": "采集期货/ETF 持仓与资金流（CFTC、ETF 份额等），每日 15:45 更新。",
    "collect_gold": "采集黄金专项监控指标（WGC/LBMA/CFTC/东财）及派生指标，每日 16:40 更新。",
    "collect_bodies": "抓取新闻/研报原文正文，供断言抽取与证据链引用。",
    "collect_daily_bars": "采集日线历史行情（A股 15:40、美股 06:30），用于趋势判断与回测。",
    "backfill_history": "每周日补全历史数据缺口并订正上游写坏的行情。",
    "extract_claims": "从新闻正文抽取可验证断言（观点/预测/数据陈述）。",
    "extract_events": "把断言归类为事件（政策/贸易/地缘/公司动作等）并关联原文。",
    "extract_claims_llm": "用 LLM 增强断言抽取（需配置 API Key），每 20 分钟补跑未处理正文。",
    "check_data_quality": "数据质检：检查新鲜度、覆盖率、连续性并写入质检结果。",
    "analyze": "运行分析引擎，生成黄金、周期、定价等分析结论与信号。",
    "cycle": "运行 EPIC-C 2.0 周期定位管线，输出长/短周期状态与历史类比。",
    "lenses": "运行 13 套研判透镜（美联储/宋鸿兵/宏观层/微观层/9 位人物），输出资产共识、分歧与规则命中。",
    "decide": "生成交易决策与计划（方向、仓位、止损），写入交易计划表。",
    "theses": "生成分析依据（论点/证据/反证/失效条件），供「分析依据」页展示。",
    "scan_alerts": "扫描预警规则并生成告警（价格、指标、事件阈值）。",
    "score_predictions": "对到期预测打分并更新命中/偏差统计。",
    "ledger": "核对原则与到期预测，产出命中/接近/不成立/缺数据四态与校准分桶。",
    "timeline": "重建 1500–2026 年表与当下坐标（数据即代码，周日 09:30 刷新）。",
    "brief_premarket": "生成盘前日报（07:30）：隔夜市场、今日日历、持仓与关注点。",
    "brief_postmarket": "生成盘后日报（21:00）：当日行情、事件驱动、持仓变化与明日展望。",
    "weekly_review": "生成周报（周日 10:00）：本周复盘、下周展望与原则核对。",
    "monthly_review": "生成月报（每月 1 日 10:00）：月度资产表现、周期位置与策略调整。",
    "brief_manual": "手动触发的简报生成入口，不参与定时调度。",
}


# Label text that no longer matches the live trigger, refreshed on startup so the
# 系统状态 page does not advertise a schedule the scheduler does not use.
LEGACY_JOB_LABELS: dict[str, set[str]] = {
    "collect_quotes": {"every 5m", "every 60s (trading hours)"},
    "collect_rates": {"every 6h"},
}


def seed_jobs() -> int:
    """Seed the full built-in job registry (idempotent; never overrides user flags)."""
    created = 0
    with SessionLocal() as session:
        legacy = session.scalar(select(Job).where(Job.name == "collect_market"))
        if legacy is not None:
            session.delete(legacy)
        for name, cron in JOBS_DEFAULT.items():
            exists = session.scalar(select(Job).where(Job.name == name))
            description = JOB_DESCRIPTIONS.get(name)
            if exists is not None:
                # Keep operator-toggled enabled flag; refresh stale/blank labels.
                if not exists.cron or exists.cron == "manual" and name != "brief_manual":
                    exists.cron = cron
                elif exists.cron in LEGACY_JOB_LABELS.get(name, ()):
                    # Labels that no longer describe the actual trigger schedule.
                    exists.cron = cron
                if description and exists.description != description:
                    # 任务说明是代码所有的文案：随启动刷新，保证与实现一致。
                    exists.description = description
                continue
            session.add(Job(name=name, cron=cron, description=description, enabled=True))
            created += 1
        session.commit()
    return created


def seed_watchlist() -> int:
    """Seed default watchlist from config (only missing symbols; user edits kept)."""
    config_path = ROOT_DIR / "config" / "default.yaml"
    if not config_path.exists():
        return 0
    with config_path.open("r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh) or {}
    items = (config.get("market") or {}).get("watchlist") or []
    created = 0
    with SessionLocal() as session:
        instruments = {
            row.symbol: row.id for row in session.scalars(select(Instrument)).all()
        }
        for index, item in enumerate(items):
            symbol = str(item.get("symbol"))
            instrument_id = instruments.get(symbol)
            if not instrument_id:
                logger.warning("watchlist symbol not found: %s", symbol)
                continue
            exists = session.scalar(
                select(WatchItem).where(WatchItem.instrument_id == instrument_id)
            )
            if exists is not None:
                continue
            session.add(
                WatchItem(
                    instrument_id=instrument_id,
                    group=item.get("group"),
                    priority=int(item.get("priority") or 3),
                    sort_order=index,
                    note=item.get("note"),
                )
            )
            created += 1
        session.commit()
    return created


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    created = seed_instruments()
    watch = seed_watchlist()
    jobs = seed_jobs()
    print(f"database ready: {settings.db_url}")
    print(f"instruments seeded: {created}")
    print(f"watchlist seeded: {watch}")
    print(f"jobs seeded: {jobs}")
    print(f"initialized at: {utcnow().isoformat()}")


if __name__ == "__main__":
    main()

"""简报里的英文标题 → 中文对照（需求 8/9 的后端辅助层）。

``app.knowledge.translate`` 的批量入口返回 ``{hash: {"zh": ..., "source": ...}}``，
但简报生成时手里只有标题原文，写 Markdown 时还要按原文取译文。这里做一层薄封装：

- 用 ``translate.text_hash()`` 做键，和种子/缓存语料共用同一条哈希规则；
- 去重、跳过空白、单次最多 ``translate.MAX_ITEMS`` 条（与 API 批量上限一致）；
- 任何异常都静默降级成「没有译文」，翻译层出问题不能拖垮日报/周报/月报；
- 返回值是 ``{原文: 中文}``，没有译文的条目不出现，调用方据此决定是否补「（中文：…）」。
"""

from __future__ import annotations

from app.knowledge import translate

__all__ = ["zh_pairs"]


def _collect(texts: list[str]) -> list[tuple[str, list[str]]]:
    """按哈希去重保序，返回 ``[(hash, [原文, ...]), ...]``，最多 MAX_ITEMS 组。"""
    buckets: dict[str, list[str]] = {}
    order: list[str] = []
    for raw in texts or []:
        if not isinstance(raw, str):
            continue
        body = translate.prepare(raw)
        if not body:
            continue
        key = translate.text_hash(body)
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        if raw not in buckets[key]:
            buckets[key].append(raw)
    return [(key, buckets[key]) for key in order[: translate.MAX_ITEMS]]


def zh_pairs(texts: list[str], allow_llm: bool = True) -> dict[str, str]:
    """把一批标题映射成 ``{原文: 中文}``，没有译文的条目不出现。

    ``allow_llm=False`` 时只查人工种子与运行期缓存——定时任务（周报/月报）走这条
    路径，不会被 LLM 调用拖住。
    """
    pairs: dict[str, str] = {}
    items = _collect(texts)
    if not items:
        return pairs
    try:
        translated = translate.translate([raw for _, raws in items for raw in raws], allow_llm=allow_llm)
    except Exception:  # noqa: BLE001 - 翻译层异常一律降级为「无中文对照」
        return pairs
    for key, raws in items:
        try:
            entry = translated.get(key) or {}
            zh = str(entry.get("zh") or "").strip()
        except Exception:  # noqa: BLE001 - 单条坏数据不影响其它条目
            continue
        if not zh:
            continue
        for raw in raws:
            pairs[raw] = zh
    return pairs

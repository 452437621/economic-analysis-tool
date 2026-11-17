"""英文内容的中文对照：本地种子/缓存优先，LLM 可用时自动补齐。

论点论据页（/theses）里的「事件驱动」「新闻与政策」两块内容来自 Federal Reserve、
ECB、EIA 等英文来源，中文用户读起来吃力。这里做一个**双层方案**：

1. 本地语料（现在就能用）：``config/translations.zh.json`` 是人工翻译的种子语料，
   随仓库提交；``data/translations-cache.json`` 是运行期缓存，LLM 翻出来的结果写进去。
2. LLM 兜底（配置 ``DEEPSEEK_API_KEY`` 后生效）：种子和缓存都没命中时，逐条调用
   ``LLMClient`` 翻译，成功即写缓存，下次直接命中。

对外只有 ``translate()`` 一个入口，且**永不抛异常**：翻不出来就返回
``{"zh": None, "source": "none"}``，前端只显示英文原文。哈希规则必须和种子生成脚本
一致，否则查不到译文的——所以种子和接口都走同一个 ``text_hash()``。
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import unicodedata
from pathlib import Path

from app.platform.config import ROOT_DIR, settings

logger = logging.getLogger(__name__)

SEED_PATH = ROOT_DIR / "config" / "translations.zh.json"
CACHE_FILENAME = "translations-cache.json"

# 单次请求的批量上限：一屏内容最多 30 条，50 是留了余量又不会撑爆上下文的折中值。
MAX_ITEMS = 50
# 单条文本上限：事件摘要常常是整段抓取文本，超过这个长度既不值得翻也很贵。
MAX_CHARS = 1200
# 中文字符占比达到这个阈值就认为「已经是中文」，原样返回、不浪费翻译额度。
CJK_MIN_RATIO = 0.3
# 一次请求里最多跑多少条 LLM 调用，避免一屏内容把当日预算一次性打光。
MAX_LLM_PER_CALL = 20
# 译文里至少要有这么多中文字符，否则视为模型没按要求翻译（比如直接回显英文）。
MIN_ZH_CHARS = 2

QUOTE_CHARS = "\"'“”‘’「」『』`"
_WHITESPACE = re.compile(r"\s+")
_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")

_SYSTEM_PROMPT = (
    "你是金融与宏观经济领域的专业译者。把用户给出的英文内容翻译成简体中文，"
    "只输出译文本身：不要解释、不要加引号、不要重复原文、不要输出 Markdown。\n"
    "要求：\n"
    "1. 术语按金融/宏观惯例翻译，例如 FOMC→联邦公开市场委员会，Treasury→财政部（或国债），"
    "Nonfarm Payrolls→非农就业人数，CPI→消费者物价指数，rate cut→降息，discount rate→贴现率，"
    "enforcement action→执法行动，minutes→会议纪要。\n"
    "2. 机构名保留英文缩写并补中文全称，例如「美联储（Federal Reserve）」。\n"
    "3. 数字、日期、金额、单位、代码、公司名和股票代码原样保留。\n"
    "4. 标题译成通顺的短句，不要逐词直译。\n"
    "5. 若内容本身已是中文，原样返回。"
)


# --------------------------------------------------------------------------- #
# 文本归一化与哈希
# --------------------------------------------------------------------------- #


def normalize(text: str | None) -> str:
    """去掉多余的空白和首尾引号，保证同一段文本只有一个哈希。"""
    if not text:
        return ""
    body = unicodedata.normalize("NFKC", str(text))
    body = _WHITESPACE.sub(" ", body).strip()
    return body.strip(QUOTE_CHARS).strip()


def prepare(text: str | None) -> str:
    """归一化并截断到 ``MAX_CHARS``，这是真正参与哈希和翻译的文本。"""
    return normalize(text)[:MAX_CHARS]


def text_hash(text: str | None) -> str:
    """sha1(归一化文本)[:16]，种子语料与接口共用同一条规则。"""
    return hashlib.sha1(prepare(text).encode("utf-8")).hexdigest()[:16]


def cjk_ratio(text: str | None) -> float:
    body = normalize(text)
    if not body:
        return 0.0
    return sum(1 for char in body if _CJK.match(char)) / len(body)


def is_chinese(text: str | None) -> bool:
    return cjk_ratio(text) >= CJK_MIN_RATIO


# --------------------------------------------------------------------------- #
# 语料加载（种子 + 运行期缓存）
# --------------------------------------------------------------------------- #

_SEED_STATE: dict[str, object] = {"path": None, "mtime": None, "data": {}}
_CACHE_STATE: dict[str, object] = {"path": None, "mtime": None, "data": {}}


def seed_path() -> Path:
    return SEED_PATH


def cache_path() -> Path:
    return Path(settings.data_dir) / CACHE_FILENAME


def _empty_payload() -> dict:
    return {"version": 1, "items": {}}


def _read_json(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError:
        return _empty_payload()
    except (OSError, ValueError) as exc:  # 缺文件/坏 JSON 都降级成空语料，不拦页面
        logger.warning("读取翻译语料失败 %s: %s", path, exc)
        return _empty_payload()
    if not isinstance(payload, dict):
        return _empty_payload()
    if not isinstance(payload.get("items"), dict):
        payload["items"] = {}
    return payload


def _load(path: Path, state: dict[str, object]) -> dict:
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return _empty_payload()
    if state["path"] == str(path) and state["mtime"] == mtime:
        return state["data"]  # type: ignore[return-value]
    payload = _read_json(path)
    state.update(path=str(path), mtime=mtime, data=payload)
    return payload


def load_seed() -> dict:
    """读 ``config/translations.zh.json``（人工种子语料）。"""
    return _load(seed_path(), _SEED_STATE)


def load_cache() -> dict:
    """读 ``data/translations-cache.json``（运行期缓存）。"""
    return _load(cache_path(), _CACHE_STATE)


def glossary() -> dict[str, str]:
    """种子语料里的术语表（可选），用于给 LLM 提示词补充固定译法。"""
    raw = load_seed().get("glossary") or {}
    if not isinstance(raw, dict):
        return {}
    return {str(key): str(value) for key, value in raw.items() if isinstance(value, str) and value}


def save_cache(entries: dict[str, str], *, path: Path | None = None) -> None:
    """把新译文并入缓存文件；先写临时文件再 replace，坏就只记日志。"""
    cleaned = {key: value.strip() for key, value in entries.items() if value and value.strip()}
    if not cleaned:
        return
    target = Path(path) if path is not None else cache_path()
    payload = _read_json(target) if target.exists() else _empty_payload()
    items = payload.setdefault("items", {})
    for key, zh in cleaned.items():
        items[key] = {"zh": zh, "src": "llm"}
    payload["version"] = 1
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_name(target.name + ".tmp")
        with temp.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        temp.replace(target)
    except OSError as exc:
        logger.warning("写入翻译缓存失败 %s: %s", target, exc)
        return
    try:
        _CACHE_STATE.update(path=str(target), mtime=target.stat().st_mtime, data=payload)
    except OSError:
        _CACHE_STATE.update(path=None, mtime=None, data={})


def _resolve_truncated(text: str) -> str | None:
    """把被截断的标题（如告警里的 60 字上限）补成库内完整标题后再查一次。

    只在近似后缀为空格/and 等明显截断时触发，且要求前缀长度 >= 24，避免误配。
    """
    body = normalize(text)
    if len(body) < 24:
        return None
    if body[-1] in "。．.!！?？;；:：)）」』】":
        return None
    try:
        from sqlalchemy import select

        from app.models.core import Document, Event
        from app.platform.db import SessionLocal

        with SessionLocal() as session:
            for model in (Document, Event):
                row = session.scalar(
                    select(model.title)
                    .where(model.title.startswith(body), model.title != body)
                    .order_by(model.title.asc())
                    .limit(1)
                )
                if row:
                    return str(row)
    except Exception:  # pragma: no cover - 缺库/缺表时安全降级
        return None
    return None


def lookup(text: str) -> dict[str, str] | None:
    """按哈希查译文，先人工种子后运行期缓存。"""
    key = text_hash(text)
    for source, payload in (("seed", load_seed()), ("cache", load_cache())):
        item = (payload.get("items") or {}).get(key)  # type: ignore[union-attr]
        if isinstance(item, dict):
            zh = str(item.get("zh") or "").strip()
            if zh:
                return {"zh": zh, "source": source}
    full = _resolve_truncated(text)
    if full and text_hash(full) != key:
        found = lookup(full)
        if found:
            return found
    return None


# --------------------------------------------------------------------------- #
# LLM 兜底
# --------------------------------------------------------------------------- #


def _llm_available() -> bool:
    try:
        return bool(settings.llm_available)
    except Exception:  # pragma: no cover - 配置异常时按「不可用」处理
        return False


def _new_client():
    from app.llm.client import LLMClient

    return LLMClient()


def _system_prompt() -> str:
    terms = glossary()
    if not terms:
        return _SYSTEM_PROMPT
    hints = "；".join(f"{src}→{zh}" for src, zh in list(terms.items())[:60])
    return f"{_SYSTEM_PROMPT}\n\n统一术语（优先采用）：{hints}"


def _llm_translate(client, text: str) -> str | None:
    messages = [
        {"role": "system", "content": _system_prompt()},
        {"role": "user", "content": text},
    ]
    try:
        result = client.chat(messages, task="translate_zh", temperature=0.0, max_tokens=1200)
    except Exception as exc:  # LLMUnavailable / 预算超限 / 网络抖动，一律降级
        logger.warning("LLM 翻译失败（task=translate_zh）: %s", exc)
        return None
    zh = normalize(getattr(result, "text", "") or "")
    if len(_CJK.findall(zh)) < MIN_ZH_CHARS:
        logger.debug("LLM 译文缺少中文，丢弃：%s", zh[:60])
        return None
    return zh


# --------------------------------------------------------------------------- #
# 对外入口
# --------------------------------------------------------------------------- #


def translate(
    texts: list[str], allow_llm: bool = True
) -> dict[str, dict[str, str | None]]:
    """批量取译文。

    返回 ``{hash: {"zh": str | None, "source": "seed"|"cache"|"llm"|"none"}}``。
    去重、单次最多 ``MAX_ITEMS`` 条、每条最多 ``MAX_CHARS`` 字符；任何异常都降级成
    ``source="none"``，绝不把 500 抛给前端。
    """
    results: dict[str, dict[str, str | None]] = {}
    prepared: dict[str, str] = {}
    order: list[str] = []
    for raw in list(texts or [])[:MAX_ITEMS]:
        if not isinstance(raw, str):
            continue
        body = prepare(raw)
        if not body:
            continue
        key = text_hash(body)
        if key not in prepared:
            prepared[key] = body
            order.append(key)

    pending: list[str] = []
    for key in order:
        body = prepared[key]
        if is_chinese(body):
            # 已有中文，原样当译文用，不再消耗翻译额度。
            results[key] = {"zh": body, "source": "seed"}
            continue
        hit = lookup(body)
        if hit:
            results[key] = {"zh": hit["zh"], "source": hit["source"]}
        else:
            pending.append(key)

    if pending and allow_llm and _llm_available():
        fresh: dict[str, str] = {}
        try:
            client = _new_client()
        except Exception as exc:  # pragma: no cover - 客户端构造失败同样降级
            logger.warning("初始化 LLM 客户端失败: %s", exc)
            client = None
        if client is not None:
            for key in pending[:MAX_LLM_PER_CALL]:
                zh = _llm_translate(client, prepared[key])
                if not zh:
                    continue
                fresh[key] = zh
                results[key] = {"zh": zh, "source": "llm"}
        if fresh:
            save_cache(fresh)

    for key in pending:
        results.setdefault(key, {"zh": None, "source": "none"})

    return results

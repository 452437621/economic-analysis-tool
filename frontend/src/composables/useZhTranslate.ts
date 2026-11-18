/**
 * 中文对照（英文事件 / 新闻 / 告警 / 日历 → 简体中文）统一 composable。
 *
 * 后端双层方案：仓库内人工种子语料 + 运行期缓存，配置 DEEPSEEK_API_KEY 后自动补译。
 * 前端只负责把「当前可见」的英文文本批量送过去，结果按 text_hash 缓存；
 * 接口失败或未命中都不报错——只显示英文原文。
 *
 * 缓存 / 去重 / 在途队列都是模块级单例：多个组件（含 ui/ZhText.vue）共享同一份结果，
 * 同一屏内的文本会被合并进同一批请求（单次 ≤ 30 条，后端 MAX_ITEMS=50 留余量）。
 */

import { computed, ref, toValue, watch, type ComputedRef, type MaybeRefOrGetter } from "vue";
import { translateTexts } from "@/api/endpoints";

/** 单次请求条数上限（后端 MAX_ITEMS=50，这里留余量）。 */
const ZH_BATCH_LIMIT = 30;
/** 与后端 MAX_CHARS 一致，超长文本不送翻译。 */
const ZH_TEXT_LIMIT = 1200;
/** 接口失败后的重试冷却，避免每个组件各触发一轮失败请求。 */
const ZH_RETRY_COOLDOWN_MS = 20_000;

const ZH_QUOTE_CHARS = /^["'“”‘’「」『』《》`]+|["'“”‘’「」『』《》`]+$/g;
/** 告警文案常带「事件：」「新闻：」前缀，作为索引键时去掉（不影响展示）。 */
const ZH_LABEL_PREFIX = /^(?:事件|新闻|公告|数据)[：:]\s*/;
const ZH_CJK = /[\u3400-\u4dbf\u4e00-\u9fff]/;
/** 只有含拉丁字母的文本才值得送翻译。 */
const ZH_LATIN = /[A-Za-z]/;

/** 归一化文本索引键：合并空白、去标签前缀、去首尾引号、截断 1200 字。 */
export function zhKey(text: string | null | undefined): string {
  const body = String(text ?? "").replace(/\s+/g, " ").trim().replace(ZH_LABEL_PREFIX, "");
  return body.replace(ZH_QUOTE_CHARS, "").trim().slice(0, ZH_TEXT_LIMIT);
}

/** 中文字符占比 ≥30% 视为已有中文，不再送翻译（与后端同一阈值）。 */
export function isChineseText(text: string): boolean {
  const body = text.replace(/\s+/g, "");
  if (!body) return false;
  const hits = body.match(ZH_CJK)?.length ?? 0;
  return hits / body.length >= 0.3;
}

/** 需要中文对照：含拉丁字母、且主体不是中文。 */
export function needsZhTranslation(text: string | null | undefined): boolean {
  const key = zhKey(text);
  return Boolean(key) && ZH_LATIN.test(key) && !isChineseText(key);
}

/* ---------- 模块级共享状态（所有组件共用一份缓存与一个请求队列） ---------- */

/** hash → 中文译文（接口返回，可能是原文语言） */
const translationByHash = ref<Map<string, string>>(new Map());
/** 归一化原文 → hash（由接口返回） */
const hashByKey = ref<Map<string, string>>(new Map());
/** 已经拿到过接口结果（命中或未命中）的文本，避免每轮轮询重复打扰后端 */
const attemptedKeys = ref<Set<string>>(new Set());
/** 排队中、尚未发出的文本 */
const queuedKeys = ref<Set<string>>(new Set());
/** 本批请求在途的文本 */
const inflightKeys = ref<Set<string>>(new Set());
/** 至少成功拿到过一次接口结果（用于「仍缺中文对照」脚注） */
const checked = ref(false);
/** 最近一次接口失败（无 key / 后端不可用）；用于 title 提示与重试冷却 */
const failed = ref(false);

let busy = false;
let flushTimer: number | null = null;
let retryAfter = 0;

/** 查一条文本的中文对照：没有 / 未命中 / 译文与原文相同（本身即中文）时返回 undefined。 */
export function zhFor(text: string | null | undefined): string | undefined {
  const key = zhKey(text);
  if (!key) return undefined;
  const hash = hashByKey.value.get(key);
  if (!hash) return undefined;
  const zh = translationByHash.value.get(hash);
  if (!zh || zhKey(zh) === key) return undefined;
  return zh;
}

/** 一条文本的中文对照状态（ZhText 用来决定是否给「暂无中文对照」提示）。 */
export type ZhStatus = "zh" | "pending" | "none" | "native" | "unknown";

export function zhStatusFor(text: string | null | undefined): ZhStatus {
  const key = zhKey(text);
  if (!key || !needsZhTranslation(key)) return "native";
  if (zhFor(key)) return "zh";
  if (inflightKeys.value.has(key) || queuedKeys.value.has(key)) return "pending";
  if (attemptedKeys.value.has(key) || failed.value) return "none";
  return "unknown";
}

function scheduleFlush(delay = 0): void {
  if (flushTimer !== null) return;
  flushTimer = window.setTimeout(() => {
    flushTimer = null;
    void flush();
  }, Math.max(0, delay));
}

/** 把待翻译文本入队（去重：已命中 / 已尝试 / 排队中 / 在途 都跳过）。 */
function enqueue(texts: readonly string[]): void {
  const next = new Set(queuedKeys.value);
  let added = false;
  for (const raw of texts) {
    const key = zhKey(raw);
    if (!needsZhTranslation(key)) continue;
    if (hashByKey.value.has(key) || attemptedKeys.value.has(key)) continue;
    if (next.has(key) || inflightKeys.value.has(key)) continue;
    next.add(key);
    added = true;
  }
  if (!added) return;
  queuedKeys.value = next;
  scheduleFlush(Date.now() < retryAfter ? retryAfter - Date.now() : 0);
}

/** 逐批取队列发送；成功更新缓存，失败静默（不标 attempted，等冷却后重试）。 */
async function flush(): Promise<void> {
  if (busy) return;
  busy = true;
  try {
    while (queuedKeys.value.size) {
      const batch = Array.from(queuedKeys.value).slice(0, ZH_BATCH_LIMIT);
      const rest = new Set(queuedKeys.value);
      for (const key of batch) rest.delete(key);
      queuedKeys.value = rest;
      inflightKeys.value = new Set([...inflightKeys.value, ...batch]);
      try {
        const response = await translateTexts(batch);
        const nextHashByKey = new Map(hashByKey.value);
        const nextByHash = new Map(translationByHash.value);
        const nextAttempted = new Set(attemptedKeys.value);
        for (const item of response.items) {
          const key = zhKey(item.text);
          if (key) nextHashByKey.set(key, item.hash);
          if (item.zh) nextByHash.set(item.hash, item.zh);
          nextAttempted.add(key || item.hash);
        }
        // 请求过的 key 一律记为 attempted：未命中的文本不再反复排队。
        for (const key of batch) nextAttempted.add(key);
        hashByKey.value = nextHashByKey;
        translationByHash.value = nextByHash;
        attemptedKeys.value = nextAttempted;
        checked.value = true;
        failed.value = false;
      } catch {
        // 翻译接口失败不打扰用户：继续显示原文，冷却后由下一次 ensure 重试。
        failed.value = true;
        retryAfter = Date.now() + ZH_RETRY_COOLDOWN_MS;
        break;
      } finally {
        const nextInflight = new Set(inflightKeys.value);
        for (const key of batch) nextInflight.delete(key);
        inflightKeys.value = nextInflight;
      }
    }
  } finally {
    busy = false;
    if (queuedKeys.value.size) {
      scheduleFlush(Date.now() < retryAfter ? retryAfter - Date.now() : 0);
    }
  }
}

export interface ZhTranslateApi {
  /** 查中文对照；未命中返回 undefined */
  zhFor: (text: string | null | undefined) => string | undefined;
  /** 查一条文本的中文对照状态 */
  statusFor: (text: string | null | undefined) => ZhStatus;
  /** 当前已登记的可见文本里，是否仍有缺中文对照的条目（至少成功请求过一次后才为真） */
  missing: ComputedRef<boolean>;
  /** 当前已登记的可见文本是否有翻译请求在途/排队 */
  pending: ComputedRef<boolean>;
  /** 手动触发加载（不传则用已登记的可见文本） */
  ensure: (texts?: readonly string[]) => void;
}

/**
 * 登记一组「当前可见」的英文文本，数据变化时自动批量补齐中文对照。
 *
 * @param source 响应式英文文本数组（ref / computed / getter 均可），会被 watch 自动触发 ensure。
 */
export function useZhTranslate(source: MaybeRefOrGetter<readonly string[] | undefined>): ZhTranslateApi {
  const texts = computed<readonly string[]>(() => toValue(source) ?? []);

  function ensure(extra?: readonly string[]): void {
    enqueue(extra ?? texts.value);
  }

  watch(texts, () => ensure(), { immediate: true });

  const pending = computed(() => {
    for (const raw of texts.value) {
      const key = zhKey(raw);
      if (!key) continue;
      if (inflightKeys.value.has(key) || queuedKeys.value.has(key)) return true;
    }
    return false;
  });

  const missing = computed(() => {
    if (!checked.value) return false;
    const seen = new Set<string>();
    for (const raw of texts.value) {
      const key = zhKey(raw);
      if (!key || seen.has(key) || !needsZhTranslation(key)) continue;
      seen.add(key);
      if (!zhFor(key)) return true;
    }
    return false;
  });

  return { zhFor, statusFor: zhStatusFor, missing, pending, ensure };
}

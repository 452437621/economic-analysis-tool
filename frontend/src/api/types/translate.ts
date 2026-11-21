/* ---------- 中文对照（英文事件 / 新闻 / 文档摘要） ---------- */

/** 译文来源：seed=仓库内人工语料，cache=运行期缓存，llm=本次自动翻译，none=未命中 */
export type TranslateSource = "seed" | "cache" | "llm" | "none";

export interface TranslateItem {
  hash: string;
  text: string;
  zh: string | null;
  source: TranslateSource;
}

export interface TranslateResponse {
  items: TranslateItem[];
  total: number;
  translated: number;
  missing: number;
}

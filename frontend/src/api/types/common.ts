/** 后端 API 响应类型（与 backend/app/api 契约保持一致，2026-11 实测） */

export interface ApiMeta {
  asof?: string | null;
  count?: number;
  with_quote?: number;
  source?: string | null;
  delay_sec?: number;
}

export interface Envelope<T> {
  data: T;
  meta?: ApiMeta;
}

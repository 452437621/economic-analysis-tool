/** 统一 API 客户端：同源请求、超时、可读错误。 */

export class ApiError extends Error {
  status: number;
  url: string;

  constructor(status: number, url: string, message?: string) {
    super(message ?? `HTTP ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.url = url;
  }
}

const DEFAULT_TIMEOUT = 15000;

interface RequestOptions extends RequestInit {
  timeout?: number;
  params?: Record<string, string | number | boolean | undefined | null>;
}

function buildUrl(url: string, params?: RequestOptions["params"]): string {
  if (!params) return url;
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const query = search.toString();
  return query ? `${url}${url.includes("?") ? "&" : "?"}${query}` : url;
}

async function request<T>(url: string, options: RequestOptions = {}): Promise<T> {
  const { timeout = DEFAULT_TIMEOUT, params, headers, ...init } = options;
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(buildUrl(url, params), {
      cache: "no-store",
      ...init,
      headers: {
        Accept: "application/json",
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...(headers ?? {}),
      },
      signal: controller.signal,
    });
    if (!response.ok) {
      let detail = "";
      try {
        const text = await response.text();
        detail = text.slice(0, 200);
      } catch {
        /* ignore */
      }
      throw new ApiError(response.status, url, detail || `HTTP ${response.status}`);
    }
    const type = response.headers.get("content-type") ?? "";
    if (type.includes("application/json")) return (await response.json()) as T;
    return (await response.text()) as unknown as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError(408, url, `请求超时（${Math.round(timeout / 1000)}s）`);
    }
    throw new ApiError(0, url, error instanceof Error ? error.message : "网络错误");
  } finally {
    window.clearTimeout(timer);
  }
}

export function getJson<T>(url: string, options?: RequestOptions): Promise<T> {
  return request<T>(url, options);
}

export function postJson<T>(url: string, body: unknown, options?: RequestOptions): Promise<T> {
  return request<T>(url, { ...options, method: "POST", body: JSON.stringify(body) });
}

export function patchJson<T>(url: string, body: unknown, options?: RequestOptions): Promise<T> {
  return request<T>(url, { ...options, method: "PATCH", body: JSON.stringify(body) });
}

export function putJson<T>(url: string, body: unknown, options?: RequestOptions): Promise<T> {
  return request<T>(url, { ...options, method: "PUT", body: JSON.stringify(body) });
}

export function deleteJson<T>(url: string, options?: RequestOptions): Promise<T> {
  return request<T>(url, { ...options, method: "DELETE" });
}

/** 生成绝对下载/打印链接（浏览器直接打开） */
export function apiUrl(path: string): string {
  return path;
}

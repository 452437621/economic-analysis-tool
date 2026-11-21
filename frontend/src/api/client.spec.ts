import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, deleteJson, getJson, patchJson, postJson } from "./client";

const originalFetch = globalThis.fetch;
const fetchMock = vi.fn();

function fakeResponse(
  body: unknown,
  status = 200,
  contentType = "application/json",
): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: {
      get: (name: string) =>
        name.toLowerCase() === "content-type" ? contentType : null,
    },
    json: async () => body,
    text: async () => (typeof body === "string" ? body : JSON.stringify(body)),
  } as unknown as Response;
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.useRealTimers();
  vi.stubGlobal("fetch", originalFetch);
});

describe("api client", () => {
  it("builds query strings and parses JSON responses", async () => {
    fetchMock.mockResolvedValue(fakeResponse({ ok: true }));

    await expect(
      getJson("/api/x", {
        params: { a: 1, b: "two", skip: undefined, empty: "" },
      }),
    ).resolves.toEqual({ ok: true });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/x?a=1&b=two");
    expect(init.cache).toBe("no-store");
    expect(init.headers.Accept).toBe("application/json");
    expect(init.headers["Content-Type"]).toBeUndefined();
  });

  it("returns plain text for non-JSON responses", async () => {
    fetchMock.mockResolvedValue(fakeResponse("plain", 200, "text/plain"));
    await expect(getJson<string>("/api/text")).resolves.toBe("plain");
  });

  it("raises ApiError with status and body detail on HTTP errors", async () => {
    fetchMock.mockResolvedValue(fakeResponse("boom detail", 500, "text/plain"));

    const error = await getJson("/api/fail").catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 500,
      url: "/api/fail",
      message: "boom detail",
    });
  });

  it("wraps network failures as status 0", async () => {
    fetchMock.mockRejectedValue(new Error("offline"));

    await expect(getJson("/api/net")).rejects.toMatchObject({
      status: 0,
      url: "/api/net",
      message: "offline",
    });
  });

  it("aborts slow requests and reports a 408 timeout", async () => {
    vi.useFakeTimers();
    fetchMock.mockImplementation(
      (_url: string, init: RequestInit) =>
        new Promise((_resolve, reject) => {
          init.signal?.addEventListener("abort", () =>
            reject(new DOMException("Aborted", "AbortError")),
          );
        }),
    );

    const pending = getJson("/api/slow", { timeout: 2000 });
    const assertion = expect(pending).rejects.toMatchObject({
      status: 408,
      url: "/api/slow",
    });
    await vi.advanceTimersByTimeAsync(2000);
    await assertion;
  });

  it("sends JSON bodies for POST/PATCH and no body for DELETE", async () => {
    fetchMock.mockResolvedValue(fakeResponse({ ok: true }));

    await postJson("/api/p", { a: 1 });
    await patchJson("/api/p/1", { b: 2 });
    await deleteJson("/api/p/1");

    const calls = fetchMock.mock.calls;
    expect(calls[0][1]).toMatchObject({ method: "POST", body: '{"a":1}' });
    expect(calls[0][1].headers["Content-Type"]).toBe("application/json");
    expect(calls[1][1]).toMatchObject({ method: "PATCH", body: '{"b":2}' });
    expect(calls[2][1]).toMatchObject({ method: "DELETE" });
  });
});

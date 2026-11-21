import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { nextTick } from "vue";
import { usePrefsStore } from "./prefs";

function mediaQueryList(matches = false): MediaQueryList {
  return {
    matches,
    media: "(prefers-color-scheme: light)",
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  } as unknown as MediaQueryList;
}

beforeEach(() => {
  localStorage.clear();
  window.history.replaceState({}, "", "/");
  vi.mocked(window.matchMedia).mockReturnValue(mediaQueryList(false));
  setActivePinia(createPinia());
});

describe("prefs store", () => {
  it("uses dark defaults when nothing is stored", () => {
    const prefs = usePrefsStore();
    // 现状：未存储主题时 themeMode 为 null（store 既有行为），resolvedTheme 回退为 dark。
    expect(prefs.themeMode).toBeNull();
    expect(prefs.updown).toBe("red");
    expect(prefs.density).toBe("standard");
    expect(prefs.refreshInterval).toBe(15);
    expect(prefs.showUnits).toBe(true);
    expect(prefs.resolvedTheme).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
  });

  it("applies theme and up/down changes to the DOM and storage", async () => {
    const prefs = usePrefsStore();

    prefs.setThemeMode("light");
    prefs.setUpdown("green");
    await nextTick();

    expect(prefs.resolvedTheme).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(document.documentElement.dataset.updown).toBe("green");
    expect(localStorage.getItem("epic-theme")).toBe("light");
    expect(localStorage.getItem("epic-updown")).toBe("green");
  });

  it("persists advanced preferences to epic-prefs", async () => {
    const prefs = usePrefsStore();

    prefs.density = "compact";
    prefs.refreshInterval = 30;
    prefs.showUnits = false;
    prefs.secondsClock = false;
    prefs.hoverHighlight = false;
    await nextTick();

    expect(JSON.parse(localStorage.getItem("epic-prefs") ?? "{}")).toEqual({
      density: "compact",
      refreshInterval: 30,
      showUnits: false,
      secondsClock: false,
      hoverHighlight: false,
    });
    expect(document.documentElement.dataset.density).toBe("compact");
    expect(document.documentElement.classList.contains("no-hover-highlight")).toBe(true);
  });

  it("hydrates stored theme and preferences", () => {
    localStorage.setItem("epic-theme", "sepia");
    localStorage.setItem("epic-updown", "green");
    localStorage.setItem(
      "epic-prefs",
      JSON.stringify({
        density: "compact",
        refreshInterval: 45,
        showUnits: false,
      }),
    );

    const prefs = usePrefsStore();
    expect(prefs.themeMode).toBe("sepia");
    expect(prefs.updown).toBe("green");
    expect(prefs.density).toBe("compact");
    expect(prefs.refreshInterval).toBe(45);
    expect(prefs.showUnits).toBe(false);
    expect(prefs.resolvedTheme).toBe("sepia");
  });

  it("resolves auto theme from matchMedia", () => {
    vi.mocked(window.matchMedia).mockReturnValue(mediaQueryList(true));

    const prefs = usePrefsStore();
    prefs.setThemeMode("auto");

    expect(prefs.resolvedTheme).toBe("light");
  });

  it("falls back for invalid theme and up/down values", () => {
    const prefs = usePrefsStore();

    prefs.setThemeMode("neon" as never);
    prefs.setUpdown("blue" as never);

    expect(prefs.themeMode).toBe("dark");
    expect(prefs.updown).toBe("red");
  });

  it("reset restores defaults and rewrites storage", async () => {
    const prefs = usePrefsStore();
    prefs.setThemeMode("light");
    prefs.refreshInterval = 99;

    prefs.reset();
    await nextTick();

    expect(prefs.themeMode).toBe("dark");
    expect(prefs.refreshInterval).toBe(15);
    expect(prefs.density).toBe("standard");
    expect(localStorage.getItem("epic-theme")).toBe("dark");
  });
});

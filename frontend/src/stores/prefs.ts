import { defineStore } from "pinia";
import { computed, ref, watch } from "vue";

export type ThemeMode = "dark" | "light" | "sepia" | "auto";
export type Updown = "red" | "green";
export type Density = "standard" | "compact";

const THEME_KEY = "epic-theme";
const UPDOWN_KEY = "epic-updown";
const PREFS_KEY = "epic-prefs";
const THEMES: ThemeMode[] = ["dark", "light", "sepia", "auto"];

interface StoredPrefs {
  density?: Density;
  refreshInterval?: number;
  showUnits?: boolean;
  secondsClock?: boolean;
  hoverHighlight?: boolean;
}

function readStorage(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* private mode */
  }
}

export const usePrefsStore = defineStore("prefs", () => {
  const params = new URLSearchParams(location.search);
  const storedPrefs: StoredPrefs = (() => {
    try {
      return JSON.parse(readStorage(PREFS_KEY) ?? "{}") as StoredPrefs;
    } catch {
      return {};
    }
  })();

  const themeMode = ref<ThemeMode>(
    (THEMES.includes((params.get("theme") ?? readStorage(THEME_KEY) ?? "dark") as ThemeMode)
      ? (params.get("theme") ?? readStorage(THEME_KEY))
      : "dark") as ThemeMode,
  );
  const updown = ref<Updown>(
    ((params.get("updown") ?? readStorage(UPDOWN_KEY) ?? "red") === "green" ? "green" : "red") as Updown,
  );
  const density = ref<Density>(storedPrefs.density === "compact" ? "compact" : "standard");
  const refreshInterval = ref<number>(storedPrefs.refreshInterval ?? 15);
  const showUnits = ref<boolean>(storedPrefs.showUnits ?? true);
  const secondsClock = ref<boolean>(storedPrefs.secondsClock ?? true);
  const hoverHighlight = ref<boolean>(storedPrefs.hoverHighlight ?? true);
  const settingsOpen = ref<boolean>(false);

  const systemLight = ref<boolean>(
    window.matchMedia?.("(prefers-color-scheme: light)").matches ?? false,
  );

  const resolvedTheme = computed<"dark" | "light" | "sepia">(() => {
    if (themeMode.value === "auto") return systemLight.value ? "light" : "dark";
    return themeMode.value === "light" || themeMode.value === "sepia" ? themeMode.value : "dark";
  });

  function applyDom(): void {
    const root = document.documentElement;
    root.dataset.theme = resolvedTheme.value;
    root.dataset.themeMode = themeMode.value;
    root.dataset.updown = updown.value;
    root.dataset.density = density.value;
    root.classList.toggle("no-hover-highlight", !hoverHighlight.value);
  }

  function persist(): void {
    writeStorage(THEME_KEY, themeMode.value);
    writeStorage(UPDOWN_KEY, updown.value);
    writeStorage(
      PREFS_KEY,
      JSON.stringify({
        density: density.value,
        refreshInterval: refreshInterval.value,
        showUnits: showUnits.value,
        secondsClock: secondsClock.value,
        hoverHighlight: hoverHighlight.value,
      } satisfies StoredPrefs),
    );
  }

  function setThemeMode(mode: ThemeMode): void {
    themeMode.value = THEMES.includes(mode) ? mode : "dark";
  }

  function setUpdown(mode: Updown): void {
    updown.value = mode === "green" ? "green" : "red";
  }

  function reset(): void {
    themeMode.value = "dark";
    updown.value = "red";
    density.value = "standard";
    refreshInterval.value = 15;
    showUnits.value = true;
    secondsClock.value = true;
    hoverHighlight.value = true;
  }

  watch([themeMode, updown, density, refreshInterval, showUnits, secondsClock, hoverHighlight], () => {
    applyDom();
    persist();
  });

  if (window.matchMedia) {
    try {
      window.matchMedia("(prefers-color-scheme: light)").addEventListener("change", (event) => {
        systemLight.value = event.matches;
      });
    } catch {
      /* older browsers */
    }
  }

  applyDom();

  return {
    themeMode,
    updown,
    density,
    refreshInterval,
    showUnits,
    secondsClock,
    hoverHighlight,
    settingsOpen,
    resolvedTheme,
    setThemeMode,
    setUpdown,
    reset,
  };
});

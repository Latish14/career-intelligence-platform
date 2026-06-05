const THEME_STORAGE_KEY = "cip-theme";

/**
 * Apply theme before React mounts to avoid flash of wrong theme.
 */
export function initTheme() {
  const stored = localStorage.getItem(THEME_STORAGE_KEY);
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const theme = stored === "dark" || stored === "light" ? stored : prefersDark ? "dark" : "light";

  document.documentElement.setAttribute("data-theme", theme);
  return theme;
}

export function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem(THEME_STORAGE_KEY, theme);
}

export function getStoredTheme() {
  return localStorage.getItem(THEME_STORAGE_KEY);
}

export { THEME_STORAGE_KEY };

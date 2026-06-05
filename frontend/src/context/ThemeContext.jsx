import { createContext, useContext, useEffect, useState } from "react";
import { applyTheme, initTheme } from "../theme/theme";

const ThemeContext = createContext(null);

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(() => initTheme());

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  const setTheme = (nextTheme) => {
    setThemeState(nextTheme === "dark" ? "dark" : "light");
  };

  const toggleTheme = () => {
    setThemeState((current) => (current === "dark" ? "light" : "dark"));
  };

  return (
    <ThemeContext.Provider value={{ theme, setTheme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within ThemeProvider");
  }
  return context;
}

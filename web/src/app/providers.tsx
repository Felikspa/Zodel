"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { Locale } from "@/lib/i18n";

type I18nCtx = {
  locale: Locale;
  setLocale: (l: Locale) => void;
};

const Ctx = createContext<I18nCtx | null>(null);

type Theme = "dark" | "light";

type ThemeCtx = {
  theme: Theme;
  setTheme: (t: Theme) => void;
  toggleTheme: () => void;
};

const ThemeCtx = createContext<ThemeCtx | null>(null);

export function Providers({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("en");
  const [theme, setThemeState] = useState<Theme>("dark");

  useEffect(() => {
    const saved = (localStorage.getItem("zodel_locale") as Locale | null) ?? null;
    if (saved === "en" || saved === "zh-CN") setLocaleState(saved);
  }, []);

  useEffect(() => {
    const saved = (localStorage.getItem("zodel_theme") as Theme | null) ?? null;
    if (saved === "dark" || saved === "light") {
      setThemeState(saved);
      document.documentElement.classList.remove("dark", "light");
      document.documentElement.classList.add(saved);
    } else {
      document.documentElement.classList.add("dark");
    }
  }, []);

  function setLocale(l: Locale) {
    setLocaleState(l);
    localStorage.setItem("zodel_locale", l);
  }

  function setTheme(t: Theme) {
    setThemeState(t);
    localStorage.setItem("zodel_theme", t);
    document.documentElement.classList.remove("dark", "light");
    document.documentElement.classList.add(t);
  }

  function toggleTheme() {
    setTheme(theme === "dark" ? "light" : "dark");
  }

  const i18nValue = useMemo(() => ({ locale, setLocale }), [locale]);
  const themeValue = useMemo(() => ({ theme, setTheme, toggleTheme }), [theme]);

  return (
    <Ctx.Provider value={i18nValue}>
      <ThemeCtx.Provider value={themeValue}>{children}</ThemeCtx.Provider>
    </Ctx.Provider>
  );
}

export function useI18n() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useI18n must be used within Providers");
  return v;
}

export function useTheme() {
  const v = useContext(ThemeCtx);
  if (!v) throw new Error("useTheme must be used within Providers");
  return v;
}

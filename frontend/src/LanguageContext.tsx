import { createContext, useContext, useState, useLayoutEffect, type ReactNode } from 'react';
import type { Lang } from './i18n';

export type Theme = 'obsidian' | 'parchment' | 'azure';

interface ContextValue {
  lang: Lang;
  setLang: (l: Lang) => void;
  theme: Theme;
  setTheme: (t: Theme) => void;
}

const LanguageContext = createContext<ContextValue>({
  lang: 'zh',
  setLang: () => {},
  theme: 'obsidian',
  setTheme: () => {},
});

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(
    () => (localStorage.getItem('zx_lang') as Lang) || 'zh'
  );
  const [theme, setThemeState] = useState<Theme>(
    () => (localStorage.getItem('zx_theme') as Theme) || 'obsidian'
  );

  const setLang = (l: Lang) => {
    setLangState(l);
    localStorage.setItem('zx_lang', l);
  };

  const setTheme = (t: Theme) => {
    setThemeState(t);
    localStorage.setItem('zx_theme', t);
  };

  useLayoutEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  return (
    <LanguageContext.Provider value={{ lang, setLang, theme, setTheme }}>
      {children}
    </LanguageContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useLang() {
  const { lang, setLang, theme, setTheme } = useContext(LanguageContext);
  return { lang, setLang, isZh: lang === 'zh', isEn: lang === 'en', theme, setTheme };
}

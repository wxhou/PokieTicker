import { createContext, useContext, useState, type ReactNode } from 'react';
import type { Lang } from './i18n';

const LanguageContext = createContext<{ lang: Lang; setLang: (l: Lang) => void }>({
  lang: 'zh',
  setLang: () => {},
});

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>(
    () => (localStorage.getItem('zx_lang') as Lang) || 'zh'
  );
  return (
    <LanguageContext.Provider value={{ lang, setLang: (l: Lang) => { setLang(l); localStorage.setItem('zx_lang', l); } }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLang() {
  const { lang, setLang } = useContext(LanguageContext);
  return { lang, setLang, isZh: lang === 'zh', isEn: lang === 'en' };
}
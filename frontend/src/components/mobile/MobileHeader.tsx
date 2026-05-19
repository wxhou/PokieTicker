import { useState, useRef, useMemo } from 'react';
import { useLang } from '../../LanguageContext';
import { t } from '../../i18n';

interface Props {
  activeTickers: string[];
  tickerNames: Record<string, string>;
  onSelect: (symbol: string) => void;
}

function IconMoon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" />
    </svg>
  );
}

function IconSun() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="5" />
      <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
    </svg>
  );
}

function IconWater() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2.69l5.66 5.66a8 8 0 11-11.31 0z" />
    </svg>
  );
}

function IconSearch() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8" />
      <path d="M21 21l-4.35-4.35" />
    </svg>
  );
}

export default function MobileHeader({ activeTickers, tickerNames, onSelect }: Props) {
  const { lang, setLang, isZh, theme, setTheme } = useLang();
  const [query, setQuery] = useState('');
  const [showResults, setShowResults] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const results = useMemo(() => {
    if (!query.trim()) return [];
    const q = query.trim().toLowerCase();
    return activeTickers
      .map((sym) => ({ symbol: sym, name: tickerNames[sym] || sym }))
      .filter(
        (item) =>
          item.symbol.toLowerCase().includes(q) ||
          item.name.toLowerCase().includes(q)
      )
      .slice(0, 8);
  }, [query, activeTickers, tickerNames]);

  const ThemeIcon = theme === 'obsidian' ? IconMoon : theme === 'parchment' ? IconSun : IconWater;

  return (
    <header className="mobile-header">
      <div className="mobile-header-top">
        <img src="/logo.svg" alt="涨讯" className="mobile-brand-logo" />
        <div className="mobile-header-actions">
          <button
            className="mobile-header-btn"
            onClick={() => {
              const next = theme === 'obsidian' ? 'parchment' : theme === 'parchment' ? 'azure' : 'obsidian';
              setTheme(next);
            }}
            title={theme}
          >
            <ThemeIcon />
          </button>
          <button
            className="mobile-header-btn lang-btn"
            onClick={() => setLang(isZh ? 'en' : 'zh')}
          >
            {isZh ? 'EN' : '中'}
          </button>
        </div>
      </div>
      <div className="mobile-search-wrapper">
        <span className="mobile-search-icon">
          <IconSearch />
        </span>
        <input
          ref={inputRef}
          className="mobile-search-input"
          type="text"
          placeholder={t('mobile.search', lang)}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => query && setShowResults(true)}
          onBlur={() => setTimeout(() => setShowResults(false), 200)}
        />
        {showResults && results.length > 0 && (
          <div className="mobile-search-dropdown">
            {results.map((item) => (
              <button
                key={item.symbol}
                className="mobile-search-item"
                onMouseDown={() => {
                  onSelect(item.symbol);
                  setQuery('');
                  setShowResults(false);
                  inputRef.current?.blur();
                }}
              >
                <span className="mobile-search-name">{item.name}</span>
                <span className="mobile-search-code">
                  {item.symbol.replace(/\.(SH|SZ)$/, '')}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>
    </header>
  );
}
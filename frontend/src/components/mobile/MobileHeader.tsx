import { useState, useRef, useMemo } from 'react';
import { useLang } from '../../LanguageContext';
import { t } from '../../i18n';

interface Props {
  activeTickers: string[];
  tickerNames: Record<string, string>;
  onSelect: (symbol: string) => void;
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
          >
            {theme === 'obsidian' ? '🌙' : theme === 'parchment' ? '☀️' : '🌊'}
          </button>
          <button
            className="mobile-header-btn"
            onClick={() => setLang(isZh ? 'en' : 'zh')}
          >
            {isZh ? 'EN' : '中'}
          </button>
        </div>
      </div>
      <div className="mobile-search-wrapper">
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
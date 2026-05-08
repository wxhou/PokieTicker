import { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { useLang } from '../LanguageContext';
import { t } from '../i18n';

interface Ticker {
  symbol: string;
  name: string;
}

interface TickerInfo {
  symbol: string;
  name: string;
}

interface Props {
  activeTickers: string[];
  selectedSymbol: string;
  onSelect: (symbol: string) => void;
  onAdd: (symbol: string) => void;
}

export default function StockSelector({ activeTickers, selectedSymbol, onSelect, onAdd }: Props) {
  const { lang } = useLang();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Ticker[]>([]);
  const [showSearch, setShowSearch] = useState(false);
  const [tickerNames, setTickerNames] = useState<Record<string, string>>({});
  const searchRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const inputRef = useRef<HTMLInputElement>(null);

  // Fetch names for active tickers
  useEffect(() => {
    axios.get('/api/stocks')
      .then((res) => {
        const map: Record<string, string> = {};
        for (const t of res.data) {
          map[t.symbol] = t.name;
        }
        setTickerNames(map);
      })
      .catch(console.error);
  }, []);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowSearch(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  function handleSearch(q: string) {
    setQuery(q);
    if (timerRef.current) clearTimeout(timerRef.current);
    if (q.length < 1) {
      setResults([]);
      setShowSearch(false);
      return;
    }
    timerRef.current = setTimeout(async () => {
      try {
        const res = await axios.get(`/api/stocks/search?q=${encodeURIComponent(q)}`);
        setResults(res.data);
        setShowSearch(true);
      } catch {
        setResults([]);
      }
    }, 300);
  }

  function handlePick(t: TickerInfo) {
    setQuery('');
    setShowSearch(false);
    if (!activeTickers.includes(t.symbol)) {
      onAdd(t.symbol);
    }
    onSelect(t.symbol);
  }

  function displayName(sym: string) {
    return tickerNames[sym] || sym;
  }

  function displayCode(sym: string) {
    return sym.replace(/\.(SH|SZ)$/, '');
  }

  return (
    <div className="stock-selector">
      <div className="ticker-tabs">
        {activeTickers.map((sym) => (
          <button
            key={sym}
            className={`ticker-tab ${sym === selectedSymbol ? 'active' : ''}`}
            onClick={() => onSelect(sym)}
            title={`${tickerNames[sym] || sym} ${sym}`}
          >
            <span className="ticker-tab-name">{displayName(sym)}</span>
            <span className="ticker-tab-code">{displayCode(sym)}</span>
          </button>
        ))}
        <button
          className="ticker-tab ticker-tab-add"
          onClick={() => inputRef.current?.focus()}
          title={t('selector.addTitle', lang)}
        >
          +
        </button>
      </div>

      <div className="search-wrapper" ref={searchRef}>
        <input
          ref={inputRef}
          type="text"
          placeholder={t('selector.search', lang)}
          value={query}
          onChange={(e) => handleSearch(e.target.value)}
          onFocus={() => results.length > 0 && setShowSearch(true)}
        />
        {showSearch && results.length > 0 && (
          <ul className="search-dropdown">
            {results.map((t) => (
              <li key={t.symbol} onClick={() => handlePick(t)}>
                <strong>{t.name}</strong>
                <span>{t.symbol}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
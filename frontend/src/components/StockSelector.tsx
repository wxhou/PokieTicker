import { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { useLang } from '../LanguageContext';
import { t } from '../i18n';

interface TickerInfo {
  symbol: string;
  name: string;
}

interface Props {
  activeTickers: string[];
  selectedSymbol: string;
  tickerChanges?: Record<string, { price: number; change: number | null }>;
  onSelect: (symbol: string) => void;
  onAdd: (symbol: string) => void;
}

function BeijingClock() {
  const [time, setTime] = useState(() => formatBJT(new Date()));

  useEffect(() => {
    const id = setInterval(() => setTime(formatBJT(new Date())), 1000);
    return () => clearInterval(id);
  }, []);

  return <span className="bj-clock">{time}</span>;
}

function formatBJT(now: Date): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: false,
  }).formatToParts(now);
  const get = (t: Intl.DateTimeFormatPartTypes) => parts.find(p => p.type === t)?.value ?? '';
  return `${get('year')}/${get('month')}/${get('day')} ${get('hour')}:${get('minute')}:${get('second')}`;
}

export default function StockSelector({ onAdd }: Props) {
  const { lang } = useLang();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<TickerInfo[]>([]);
  const [showSearch, setShowSearch] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const inputRef = useRef<HTMLInputElement>(null);

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
        setShowSearch(res.data.length > 0);
      } catch {
        setResults([]);
      }
    }, 300);
  }

  function handlePick(t: TickerInfo) {
    setQuery('');
    setShowSearch(false);
    onAdd(t.symbol);
  }

  return (
    <div className="stock-selector" ref={searchRef}>
      <div className="search-wrapper">
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
      <BeijingClock />
    </div>
  );
}
import { useState, useEffect, useRef } from 'react';
import axios from 'axios';

interface Ticker {
  symbol: string;
  name: string;
  sector?: string;
}

interface Props {
  activeTickers: string[];
  selectedSymbol: string;
  onSelect: (symbol: string) => void;
  onAdd: (symbol: string) => void;
}

const GROUPS: Record<string, string[]> = {
  '科技': ['002415', '000063', '002371', '688981', '688256', '688396', '002049', '300223', '688521'],
  '新能源': ['300750', '002594', '300014', '688005', '002812', '600438', '300274', '600905'],
  '白酒': ['600519', '000858', '000568', '600809', '002304', '600702', '000596', '603369'],
  '医药': ['600276', '000538', '300760', '300122', '688180', '603259', '300015', '002007'],
  '消费': ['000568', '600887', '002304', '000333', '603288', '600600', '002557', '000895'],
  '半导体': ['688981', '688256', '688396', '002371', '002049', '688521', '688008', '688012'],
  '金融': ['600036', '601318', '600016', '601166', '600000', '000001', '601398', '601288'],
  '地产': ['000002', '600048', '001979', '600606', '600383', '601155', '000671', '600823'],
  '军工': ['002025', '600893', '600760', '002013', '600316', '600862', '688185', '000738'],
  'AI': ['300024', '603019', '002410', '300229', '688041', '300678', '688787', '300308'],
  '其他': [],
};

export default function StockSelector({ activeTickers, selectedSymbol, onSelect, onAdd }: Props) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Ticker[]>([]);
  const [showSearch, setShowSearch] = useState(false);
  const [showPanel, setShowPanel] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowSearch(false);
      }
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setShowPanel(false);
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

  function handlePick(ticker: Ticker) {
    setQuery('');
    setShowSearch(false);
    setShowPanel(false);
    if (!activeTickers.includes(ticker.symbol)) {
      onAdd(ticker.symbol);
    }
    onSelect(ticker.symbol);
  }

  function handleSelectTicker(sym: string) {
    setShowPanel(false);
    onSelect(sym);
  }

  // Build groups filtered to only tickers that exist in our data
  const activeSet = new Set(activeTickers);
  const renderedGroups = Object.entries(GROUPS)
    .map(([label, symbols]) => ({
      label,
      symbols: symbols.filter((s) => activeSet.has(s)),
    }))
    .filter((g) => g.symbols.length > 0);

  const assigned = new Set(renderedGroups.flatMap((g) => g.symbols));
  const ungrouped = activeTickers.filter((s) => !assigned.has(s)).sort();
  if (ungrouped.length > 0) {
    const otherGroup = renderedGroups.find((g) => g.label === '其他');
    if (otherGroup) {
      otherGroup.symbols.push(...ungrouped);
    } else {
      renderedGroups.push({ label: '其他', symbols: ungrouped });
    }
  }

  return (
    <div className="stock-selector">
      {/* Current ticker button — click to open dropdown */}
      <div className="ticker-dropdown-wrapper" ref={panelRef}>
        <button
          className="ticker-current"
          onClick={() => setShowPanel((v) => !v)}
        >
          <span className="ticker-current-symbol">{selectedSymbol || '---'}</span>
          <span className={`ticker-arrow ${showPanel ? 'open' : ''}`}>&#9662;</span>
        </button>

        {showPanel && (
          <div className="ticker-panel">
            {renderedGroups.map((group) => (
              <div className="ticker-panel-group" key={group.label}>
                <div className="ticker-panel-group-label">{group.label}</div>
                <div className="ticker-panel-group-items">
                  {group.symbols.map((sym) => (
                    <button
                      key={sym}
                      className={`ticker-panel-item ${sym === selectedSymbol ? 'active' : ''}`}
                      onClick={() => handleSelectTicker(sym)}
                    >
                      {sym}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Search */}
      <div className="search-wrapper" ref={searchRef}>
        <input
          type="text"
          placeholder="搜索股票..."
          value={query}
          onChange={(e) => handleSearch(e.target.value)}
          onFocus={() => results.length > 0 && setShowSearch(true)}
        />
        {showSearch && results.length > 0 && (
          <ul className="search-dropdown">
            {results.map((t) => (
              <li key={t.symbol} onClick={() => handlePick(t)}>
                <strong>{t.symbol}</strong> <span>{t.name}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

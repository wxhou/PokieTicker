import { useState, useRef, useEffect } from 'react';

interface Props {
  activeTickers: string[];
  tickerNames: Record<string, string>;
  tickerChanges: Record<string, { price: number; change: number | null }>;
  selectedSymbol: string;
  onSelect: (symbol: string) => void;
}

function IconTrendUp() {
  return (
    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
      <polyline points="16 7 22 7 22 13" />
    </svg>
  );
}

function IconTrendDown() {
  return (
    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="22 17 13.5 8.5 8.5 13.5 2 7" />
      <polyline points="16 17 22 17 22 11" />
    </svg>
  );
}

function IconChevronDown() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}

function IconSearch() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8" />
      <path d="M21 21l-4.35-4.35" />
    </svg>
  );
}

export default function MobileStockTabs({
  activeTickers,
  tickerNames,
  tickerChanges,
  selectedSymbol,
  onSelect,
}: Props) {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const selectedName = tickerNames[selectedSymbol] || selectedSymbol.replace(/\.(SH|SZ)$/, '');
  const selectedPrice = tickerChanges[selectedSymbol]?.price;
  const selectedChange = tickerChanges[selectedSymbol]?.change;

  // Filter tickers based on query
  const filteredTickers = query.trim()
    ? activeTickers.filter(sym => {
        const name = tickerNames[sym] || '';
        const code = sym.replace(/\.(SH|SZ)$/, '');
        const q = query.toLowerCase();
        return name.toLowerCase().includes(q) || code.toLowerCase().includes(q);
      })
    : activeTickers;

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  // Auto-scroll to selected tab in horizontal mode (when dropdown closed)
  useEffect(() => {
    if (isOpen) return;
    const container = scrollRef.current;
    if (!container) return;
    const active = container.querySelector('.mstock-tab.active') as HTMLElement;
    if (active) {
      active.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
    }
  }, [selectedSymbol, isOpen]);

  // If many tickers, use dropdown mode
  if (activeTickers.length > 12) {
    return (
      <div className="mstock-selector" ref={dropdownRef}>
        <button
          className="mstock-selector-trigger"
          onClick={() => setIsOpen(!isOpen)}
        >
          <div className="mstock-selector-info">
            <span className="mstock-selector-name">{selectedName}</span>
            <span className="mstock-selector-code">{selectedSymbol.replace(/\.(SH|SZ)$/, '')}</span>
          </div>
          <div className="mstock-selector-right">
            {selectedPrice != null && (
              <span className="mstock-selector-price">{selectedPrice.toFixed(2)}</span>
            )}
            {selectedChange != null && (
              <span className={`mstock-selector-change ${selectedChange >= 0 ? 'up' : 'down'}`}>
                {selectedChange >= 0 ? '+' : ''}{selectedChange.toFixed(2)}%
              </span>
            )}
            <IconChevronDown />
          </div>
        </button>

        {isOpen && (
          <div className="mstock-selector-dropdown">
            <div className="mstock-selector-search">
              <IconSearch />
              <input
                type="text"
                placeholder="搜索股票..."
                value={query}
                onChange={e => setQuery(e.target.value)}
                autoFocus
              />
            </div>
            <div className="mstock-selector-list">
              {filteredTickers.slice(0, 50).map(sym => {
                const change = tickerChanges[sym]?.change;
                const price = tickerChanges[sym]?.price;
                const name = tickerNames[sym] || sym;
                return (
                  <button
                    key={sym}
                    className={`mstock-selector-item ${sym === selectedSymbol ? 'active' : ''}`}
                    onClick={() => {
                      onSelect(sym);
                      setIsOpen(false);
                      setQuery('');
                    }}
                  >
                    <span className="mstock-selector-item-name">{name}</span>
                    <span className="mstock-selector-item-code">{sym.replace(/\.(SH|SZ)$/, '')}</span>
                    <span className="mstock-selector-item-right">
                      {price != null && <span className="mstock-selector-item-price">{price.toFixed(2)}</span>}
                      {change != null && (
                        <span className={`mstock-selector-item-change ${change >= 0 ? 'up' : 'down'}`}>
                          {change >= 0 ? '+' : ''}{change.toFixed(2)}%
                        </span>
                      )}
                    </span>
                  </button>
                );
              })}
              {filteredTickers.length === 0 && (
                <div className="mstock-selector-empty">未找到匹配的股票</div>
              )}
            </div>
          </div>
        )}
      </div>
    );
  }

  // Horizontal scroll tabs for fewer tickers
  return (
    <div className="mstock-tabs" ref={scrollRef}>
      {activeTickers.map((sym) => {
        const change = tickerChanges[sym]?.change;
        const price = tickerChanges[sym]?.price;
        return (
          <button
            key={sym}
            className={`mstock-tab ${sym === selectedSymbol ? 'active' : ''}`}
            onClick={() => onSelect(sym)}
          >
            <span className="mstock-tab-name">{tickerNames[sym] || sym.replace(/\.(SH|SZ)$/, '')}</span>
            {price != null && <span className="mstock-tab-price">{price.toFixed(2)}</span>}
            {change != null && (
              <span className={`mstock-tab-change ${change >= 0 ? 'up' : 'down'}`}>
                {change >= 0 ? <IconTrendUp /> : <IconTrendDown />}
                {change >= 0 ? '+' : ''}{change.toFixed(2)}%
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
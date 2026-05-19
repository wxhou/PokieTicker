import { useRef, useEffect } from 'react';

interface Props {
  activeTickers: string[];
  tickerNames: Record<string, string>;
  tickerChanges: Record<string, { price: number; change: number | null }>;
  selectedSymbol: string;
  onSelect: (symbol: string) => void;
}

export default function MobileStockTabs({
  activeTickers,
  tickerNames,
  tickerChanges,
  selectedSymbol,
  onSelect,
}: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Auto-scroll to selected tab
    const container = scrollRef.current;
    if (!container) return;
    const active = container.querySelector('.mstock-tab.active') as HTMLElement;
    if (active) {
      active.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
    }
  }, [selectedSymbol]);

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
                {change >= 0 ? '+' : ''}{change.toFixed(2)}%
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
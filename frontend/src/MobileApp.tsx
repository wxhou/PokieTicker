import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import MobileHeader from './components/mobile/MobileHeader';
import MobileStockTabs from './components/mobile/MobileStockTabs';
import MobileBottomNav, { type MobileRoute } from './components/mobile/MobileBottomNav';
import MobileHome from './components/mobile/MobileHome';
import MobileSettings from './components/mobile/MobileSettings';
import EventCalendar from './components/EventCalendar';
import Portfolio from './components/Portfolio';
import './MobileApp.css';

const LAST_SYMBOL_KEY = 'zx_last_symbol';

export default function MobileApp() {
  const [route, setRoute] = useState<MobileRoute>('home');
  const [activeTickers, setActiveTickers] = useState<string[]>([]);
  const [tickerNames, setTickerNames] = useState<Record<string, string>>({});
  const [tickerChanges, setTickerChanges] = useState<Record<string, { price: number; change: number | null }>>({});
  const [selectedSymbol, setSelectedSymbol] = useState('');
  const [symbolKey, setSymbolKey] = useState(0);

  useEffect(() => {
    axios
      .get('/api/stocks')
      .then((res) => {
        const tickers = (res.data as { symbol: string; last_ohlc_fetch: boolean; last_price?: number; change_pct?: number | null; name?: string }[])
          .filter((t) => t.last_ohlc_fetch);
        const symbols = tickers.map((t) => t.symbol);
        setActiveTickers(symbols);
        const names: Record<string, string> = {};
        const changes: Record<string, { price: number; change: number | null }> = {};
        for (const t of tickers) {
          names[t.symbol] = t.name || t.symbol;
          if (t.last_price != null) changes[t.symbol] = { price: t.last_price, change: t.change_pct ?? null };
        }
        setTickerNames(names);
        setTickerChanges(changes);
        const last = localStorage.getItem(LAST_SYMBOL_KEY);
        const initial = (last && symbols.includes(last)) ? last : symbols[0] ?? '';
        if (initial) {
          setSelectedSymbol(initial);
          localStorage.setItem(LAST_SYMBOL_KEY, initial);
        }
      })
      .catch(() => {});
  }, []);

  // Real-time quotes
  useEffect(() => {
    function isMarketOpen(): boolean {
      const now = new Date();
      const day = now.getDay();
      if (day === 0 || day === 6) return false;
      const h = now.getHours();
      const m = now.getMinutes();
      const tm = h * 60 + m;
      return (tm >= 570 && tm <= 690) || (tm >= 780 && tm <= 900);
    }
    if (!isMarketOpen()) return;

    const interval = setInterval(() => {
      if (!isMarketOpen()) return;
      axios
        .get('/api/stocks/quotes')
        .then((res) => {
          const quotes = res.data as { code: string; price: number; change_pct: number }[];
          if (!quotes || quotes.length === 0) return;
          setTickerChanges((prev) => {
            const next = { ...prev };
            for (const q of quotes) {
              if (q.price <= 0) continue;
              const resolved =
                q.code.startsWith('6') ? `${q.code}.SH` :
                q.code.startsWith('0') || q.code.startsWith('3') ? `${q.code}.SZ` :
                q.code;
              next[resolved] = { price: q.price, change: q.change_pct };
            }
            return next;
          });
        })
        .catch(() => {});
    }, 30000);

    return () => clearInterval(interval);
  }, []);

  const handleSelectSymbol = useCallback((symbol: string) => {
    setSelectedSymbol(symbol);
    localStorage.setItem(LAST_SYMBOL_KEY, symbol);
    setRoute('home');
    setSymbolKey(k => k + 1);
  }, []);

  function renderContent() {
    switch (route) {
      case 'home':
        return (
          <MobileHome
            key={symbolKey}
            selectedSymbol={selectedSymbol}
            tickerChanges={tickerChanges}
            tickerNames={tickerNames}
          />
        );
      case 'events':
        return (
          <div className="mobile-events">
            <EventCalendar
              onSelectSymbol={(sym) => {
                setSelectedSymbol(sym);
                localStorage.setItem(LAST_SYMBOL_KEY, sym);
                setRoute('home');
              }}
            />
          </div>
        );
      case 'portfolio':
        return (
          <div className="mobile-portfolio">
            <Portfolio onBack={() => setRoute('home')} />
          </div>
        );
      case 'settings':
        return <MobileSettings />;
    }
  }

  return (
    <div className="mobile-app">
      <MobileHeader
        activeTickers={activeTickers}
        tickerNames={tickerNames}
        onSelect={handleSelectSymbol}
      />
      <MobileStockTabs
        activeTickers={activeTickers}
        tickerNames={tickerNames}
        tickerChanges={tickerChanges}
        selectedSymbol={selectedSymbol}
        onSelect={handleSelectSymbol}
      />
      <main className="mobile-content">{renderContent()}</main>
      <MobileBottomNav route={route} onNavigate={setRoute} />
    </div>
  );
}
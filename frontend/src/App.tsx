import { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import StockSelector from './components/StockSelector';
import CandlestickChart from './components/CandlestickChart';
import NewsPanel from './components/NewsPanel';
import NewsCategoryPanel from './components/NewsCategoryPanel';
import RangeAnalysisPanel from './components/RangeAnalysisPanel';
import RangeQueryPopup from './components/RangeQueryPopup';
import RangeNewsPanel from './components/RangeNewsPanel';
import SimilarDaysPanel from './components/SimilarDaysPanel';
import PredictionPanel from './components/PredictionPanel';
import Portfolio from './components/Portfolio';
import { Agentation } from 'agentation';
import { LanguageProvider, useLang } from './LanguageContext';
import { t } from './i18n';
import './App.css';

const LAST_SYMBOL_KEY = 'zx_last_symbol';

interface RangeSelection {
  startDate: string;
  endDate: string;
  priceChange?: number;
  popupX?: number;
  popupY?: number;
}

interface ArticleSelection {
  newsId: string;
  date: string;
}

type Route = 'main' | 'portfolio';

function App() {
  const { lang, setLang, isZh, theme, setTheme } = useLang();
  const [route, setRoute] = useState<Route>('main');
  const [activeTickers, setActiveTickers] = useState<string[]>([]);
  const [tickerChanges, setTickerChanges] = useState<Record<string, { price: number; change: number | null }>>({});
  const [selectedSymbol, setSelectedSymbol] = useState('');
  const [hoveredDate, setHoveredDate] = useState<string | null>(null);
  const [hoveredOhlc, setHoveredOhlc] = useState<{
    date: string;
    open: number;
    high: number;
    low: number;
    close: number;
    change: number;
  } | null>(null);
  const [selectedRange, setSelectedRange] = useState<RangeSelection | null>(null);
  const [rangeQuestion, setRangeQuestion] = useState<string | null>(null);
  const [selectedDay, setSelectedDay] = useState<string | null>(null);
  const [selectedArticle, setSelectedArticle] = useState<ArticleSelection | null>(null);

  // Locked article state (click-to-lock)
  const [lockedArticle, setLockedArticle] = useState<ArticleSelection | null>(null);

  // News category filter
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [activeCategoryIds, setActiveCategoryIds] = useState<string[]>([]);
  const [activeCategoryColor, setActiveCategoryColor] = useState<string | null>(null);

  // Chart area ref for popup positioning
  const chartAreaRef = useRef<HTMLDivElement>(null);
  const [chartRect, setChartRect] = useState<DOMRect | undefined>(undefined);
  const [connError, setConnError] = useState(false);
  const [isLive, setIsLive] = useState(false);

  useEffect(() => {
    axios
      .get('/api/stocks')
      .then((res) => {
        setConnError(false);
        const tickers = (res.data as { symbol: string; last_ohlc_fetch: boolean; last_price?: number; change_pct?: number | null }[])
          .filter((t) => t.last_ohlc_fetch);
        const symbols = tickers.map((t) => t.symbol);
        setActiveTickers(symbols);
        const changes: Record<string, { price: number; change: number | null }> = {};
        for (const t of tickers) {
          if (t.last_price != null) changes[t.symbol] = { price: t.last_price, change: t.change_pct ?? null };
        }
        setTickerChanges(changes);
        // Priority: URL param > localStorage > first ticker
        const urlSymbol = new URLSearchParams(window.location.search).get('symbol');
        const last = localStorage.getItem(LAST_SYMBOL_KEY);
        const initial = (urlSymbol && symbols.includes(urlSymbol)) ? urlSymbol
          : (last && symbols.includes(last)) ? last
          : (symbols[0] ?? '');
        if (initial) {
          setSelectedSymbol(initial);
          localStorage.setItem(LAST_SYMBOL_KEY, initial);
        }
      })
      .catch(() => setConnError(true));
  }, []);

  // Real-time quotes polling during market hours
  useEffect(() => {
    function isMarketOpen(): boolean {
      const now = new Date();
      const day = now.getDay();
      if (day === 0 || day === 6) return false;
      const h = now.getHours();
      const m = now.getMinutes();
      const t = h * 60 + m;
      // 9:30-11:30 or 13:00-15:00 CST
      return (t >= 570 && t <= 690) || (t >= 780 && t <= 900);
    }

    if (!isMarketOpen()) return;

    // Initial fetch
    axios
      .get('/api/stocks/quotes')
      .then((res) => {
        const quotes = res.data as { code: string; price: number; change_pct: number }[];
        if (!quotes || quotes.length === 0) return;
        setIsLive(true);
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

    const interval = setInterval(() => {
      if (!isMarketOpen()) { setIsLive(false); return; }
      axios
        .get('/api/stocks/quotes')
        .then((res) => {
          const quotes = res.data as { code: string; price: number; change_pct: number }[];
          if (!quotes || quotes.length === 0) return;
          setIsLive(true);
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
        .catch(() => { setIsLive(false); });
    }, 30000);

    return () => { clearInterval(interval); setIsLive(false); };
  }, []);

  // Update chartRect when range is selected (for popup positioning)
  useEffect(() => {
    if (selectedRange && chartAreaRef.current) {
      setChartRect(chartAreaRef.current.getBoundingClientRect());
    }
  }, [selectedRange]);

  const handleHover = useCallback(
    (date: string | null, ohlc?: { date: string; open: number; high: number; low: number; close: number; change: number }) => {
      // Don't update hovered date when locked
      if (!lockedArticle) {
        setHoveredDate(date);
      }
      setHoveredOhlc(ohlc || null);
    },
    [lockedArticle]
  );

  const handleRangeSelect = useCallback((range: RangeSelection | null) => {
    setSelectedRange(range);
    setRangeQuestion(null);
    if (range) {
      setSelectedDay(null);
      setSelectedArticle(null);
      setLockedArticle(null);
    }
  }, []);

  const handleArticleSelect = useCallback((article: ArticleSelection | null) => {
    if (article === null) {
      // Unlock
      setLockedArticle(null);
      setSelectedArticle(null);
      return;
    }
    // Toggle: click same dot → unlock, different dot → lock new
    setLockedArticle((prev) => {
      if (prev && prev.newsId === article.newsId) {
        // Unlock
        setSelectedArticle(null);
        return null;
      }
      // Lock new
      setSelectedArticle(article);
      setSelectedRange(null);
      setRangeQuestion(null);
      setSelectedDay(null);
      setHoveredDate(article.date);
      return article;
    });
  }, []);

  const handleDayClick = useCallback((date: string) => {
    setSelectedDay(date);
    setSelectedRange(null);
    setRangeQuestion(null);
    setSelectedArticle(null);
    setLockedArticle(null);
  }, []);

  const handleRangeAsk = useCallback((question: string) => {
    setRangeQuestion(question);
  }, []);

  const handleCategoryChange = useCallback((category: string | null, articleIds: string[], color?: string) => {
    setActiveCategory(category);
    setActiveCategoryIds(articleIds);
    setActiveCategoryColor(color ?? null);
  }, []);

  function handleSelectSymbol(symbol: string) {
    setSelectedSymbol(symbol);
    localStorage.setItem(LAST_SYMBOL_KEY, symbol);
    setHoveredDate(null);
    setHoveredOhlc(null);
    setSelectedRange(null);
    setRangeQuestion(null);
    setSelectedDay(null);
    setSelectedArticle(null);
    setLockedArticle(null);
    setActiveCategory(null);
    setActiveCategoryIds([]);
    setActiveCategoryColor(null);
  }

  function handleAddTicker(symbol: string) {
    if (!activeTickers.includes(symbol)) {
      setActiveTickers((prev) => [...prev, symbol]);
      axios.post('/api/stocks', { symbol }).catch(console.error);
    }
  }

  // Effective date for NewsPanel: locked takes priority
  const effectiveDate = lockedArticle?.date ?? hoveredDate;
  const isLocked = lockedArticle !== null;

  // Right panel priority: rangeQuestion > rangeNews > selectedDay > default NewsPanel
  function renderRightPanel() {
    if (selectedRange && rangeQuestion) {
      return (
        <RangeAnalysisPanel
          symbol={selectedSymbol}
          startDate={selectedRange.startDate}
          endDate={selectedRange.endDate}
          question={rangeQuestion}
          onClear={() => {
            setSelectedRange(null);
            setRangeQuestion(null);
          }}
        />
      );
    }
    if (selectedRange && !rangeQuestion) {
      return (
        <RangeNewsPanel
          symbol={selectedSymbol}
          startDate={selectedRange.startDate}
          endDate={selectedRange.endDate}
          priceChange={selectedRange.priceChange}
          onClose={() => setSelectedRange(null)}
          onAskAI={handleRangeAsk}
        />
      );
    }
    if (selectedDay) {
      return (
        <SimilarDaysPanel
          symbol={selectedSymbol}
          date={selectedDay}
          onClose={() => setSelectedDay(null)}
        />
      );
    }
    return (
      <>
        <NewsPanel
          symbol={selectedSymbol}
          hoveredDate={effectiveDate}
          onFindSimilar={() => {
            if (effectiveDate) handleDayClick(effectiveDate);
          }}
          highlightedNewsId={selectedArticle?.newsId || null}
          isLocked={isLocked}
          onUnlock={() => {
            setLockedArticle(null);
            setSelectedArticle(null);
          }}
          highlightedCategoryIds={activeCategoryIds.length > 0 ? activeCategoryIds : undefined}
        />
      </>
    );
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <h1 className="brand-name">涨讯</h1>
          <div className="brand-divider" />
          <span className="brand-sub">{t('brand.sub', lang)}</span>
        </div>
        <StockSelector
          activeTickers={activeTickers}
          selectedSymbol={selectedSymbol}
          tickerChanges={tickerChanges}
          onSelect={handleSelectSymbol}
          onAdd={handleAddTicker}
        />
        {isLive && <span className="live-indicator" title={isZh ? '行情实时更新中' : 'Live quotes'} />}
        {selectedRange ? (
          <div className="header-ohlc">
            <span className="ohlc-date">{selectedRange.startDate} ~ {selectedRange.endDate}</span>
            <span className="range-badge">{t('range.selected', lang)}</span>
          </div>
        ) : hoveredOhlc ? (
          <div className="header-ohlc">
            <span className="ohlc-date">{hoveredOhlc.date}</span>
            <span className="ohlc-label">{t('ohlc.open', lang)}</span>
            <span className="ohlc-val">{hoveredOhlc.open.toFixed(2)}</span>
            <span className="ohlc-sep" />
            <span className="ohlc-label">{t('ohlc.high', lang)}</span>
            <span className="ohlc-val">{hoveredOhlc.high.toFixed(2)}</span>
            <span className="ohlc-sep" />
            <span className="ohlc-label">{t('ohlc.low', lang)}</span>
            <span className="ohlc-val">{hoveredOhlc.low.toFixed(2)}</span>
            <span className="ohlc-sep" />
            <span className="ohlc-label">{t('ohlc.close', lang)}</span>
            <span className="ohlc-val">{hoveredOhlc.close.toFixed(2)}</span>
            <span className={`ohlc-change ${hoveredOhlc.change >= 0 ? 'up' : 'down'}`}>
              {hoveredOhlc.change >= 0 ? '+' : ''}
              {hoveredOhlc.change.toFixed(2)}%
            </span>
          </div>
        ) : null}
        <div className="header-right">
          <button
            className="nav-btn theme-toggle"
            onClick={() => {
              const next = theme === 'obsidian' ? 'parchment' : theme === 'parchment' ? 'azure' : 'obsidian';
              setTheme(next);
            }}
            title="切换主题"
          >
            {theme === 'obsidian' ? '🌙' : theme === 'parchment' ? '☀️' : '🌊'}
          </button>
          <button
            className="nav-btn lang-toggle"
            onClick={() => setLang(isZh ? 'en' : 'zh')}
            title={isZh ? 'Switch to English' : '切换到中文'}
          >
            {isZh ? 'EN' : '中'}
          </button>
          <button
            className="nav-btn"
            onClick={() => setRoute(route === 'portfolio' ? 'main' : 'portfolio')}
          >
            {route === 'portfolio' ? t('nav.back', lang) : t('nav.portfolio', lang)}
          </button>
          <a href="https://github.com/wxhou/PokieTicker" target="_blank" rel="noopener noreferrer" className="header-link header-github">
            <svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor">
              <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
            </svg>
          </a>
        </div>
      </header>

      <main className={`app-main ${route === 'portfolio' ? 'portfolio-route' : ''}`}>
        {route === 'portfolio' ? (
          <div className="portfolio-full">
            <Portfolio onBack={() => setRoute('main')} />
          </div>
        ) : (
        <div className="chart-area" ref={chartAreaRef}>
          {connError ? (
            <div className="chart-placeholder">{t('chart.connError', lang)}</div>
          ) : selectedSymbol ? (
            <>
              <CandlestickChart
                symbol={selectedSymbol}
                livePrice={tickerChanges[selectedSymbol]?.price ?? null}
                lockedNewsId={lockedArticle?.newsId ?? null}
                highlightedArticleIds={activeCategoryIds.length > 0 ? activeCategoryIds : null}
                highlightColor={activeCategoryColor}
                onHover={handleHover}
                onRangeSelect={handleRangeSelect}
                onArticleSelect={handleArticleSelect}
                onDayClick={handleDayClick}
              />
              {selectedRange && !rangeQuestion && (
                <RangeQueryPopup
                  range={selectedRange}
                  chartRect={chartRect}
                  onAsk={handleRangeAsk}
                  onClose={() => setSelectedRange(null)}
                />
              )}
            </>
          ) : (
            <div className="chart-placeholder">{t('chart.placeholder', lang)}</div>
          )}
        </div>
        )}
        {selectedSymbol && (
          <>
          <div className="prediction-area">
            <PredictionPanel symbol={selectedSymbol} />
          </div>
          <div className="news-area">
            <NewsCategoryPanel
              symbol={selectedSymbol}
              activeCategory={activeCategory}
              onCategoryChange={handleCategoryChange}
            />
            {renderRightPanel()}
          </div>
          </>
        )}
      </main>

      <footer className="global-disclaimer">
        {t('footer.disclaimer', lang)}
      </footer>
      <Agentation />
    </div>
  );
}

export default function AppWithLang() {
  return (
    <LanguageProvider>
      <App />
    </LanguageProvider>
  );
}

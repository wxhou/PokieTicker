import { useState, useCallback, useRef } from 'react';
import CandlestickChart from '../CandlestickChart';
import NewsPanel from '../NewsPanel';
import NewsCategoryPanel from '../NewsCategoryPanel';
import AttributionCard from './AttributionCard';
import BottomSheet from './BottomSheet';
import SimilarDaysPanel from '../SimilarDaysPanel';
import { useLang } from '../../LanguageContext';
import { t } from '../../i18n';

export default function MobileHome({
  selectedSymbol,
  tickerChanges,
  tickerNames,
}: {
  selectedSymbol: string;
  tickerChanges: Record<string, { price: number; change: number | null }>;
  tickerNames: Record<string, string>;
}) {
  const { lang } = useLang();
  const [hoveredDate, setHoveredDate] = useState<string | null>(null);
  const [selectedDay, setSelectedDay] = useState<string | null>(null);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [activeCategoryIds, setActiveCategoryIds] = useState<string[]>([]);
  const newsRef = useRef<HTMLDivElement | null>(null);

  const handleHover = useCallback(
    (date: string | null) => {
      setHoveredDate(date);
    },
    []
  );

  const handleCategoryChange = useCallback(
    (category: string | null, articleIds: string[], _color?: string) => {
      setActiveCategory(category);
      setActiveCategoryIds(articleIds);
    },
    []
  );

  const price = tickerChanges[selectedSymbol]?.price;
  const change = tickerChanges[selectedSymbol]?.change;
  const name = tickerNames[selectedSymbol] || selectedSymbol.replace(/\.(SH|SZ)$/, '');

  return (
    <div className="mobile-home">
      {/* Stock info row */}
      {selectedSymbol && (
        <div className="mobile-stock-info">
          <div className="mobile-stock-name">{name}</div>
          <div className="mobile-stock-detail">
            <span className="mobile-stock-code">{selectedSymbol.replace(/\.(SH|SZ)$/, '')}</span>
            {price != null && <span className="mobile-stock-price">{price.toFixed(2)}</span>}
            {change != null && (
              <span className={`mobile-stock-change ${change >= 0 ? 'up' : 'down'}`}>
                {change >= 0 ? '+' : ''}{change.toFixed(2)}%
              </span>
            )}
          </div>
        </div>
      )}

      {/* Chart - moved before attribution for better visual hierarchy */}
      <div className="mobile-chart-area">
        {selectedSymbol ? (
          <CandlestickChart
            symbol={selectedSymbol}
            livePrice={tickerChanges[selectedSymbol]?.price ?? null}
            lockedNewsId={null}
            highlightedArticleIds={activeCategoryIds.length > 0 ? activeCategoryIds : null}
            onHover={handleHover}
            onRangeSelect={() => {}}
            onArticleSelect={() => {}}
            onDayClick={(date: string) => setSelectedDay(date)}
          />
        ) : (
          <div className="mobile-chart-placeholder">{t('chart.placeholder', lang)}</div>
        )}
      </div>

      {/* Attribution card - after chart */}
      {selectedSymbol && (
        <AttributionCard symbol={selectedSymbol} newsRef={newsRef} />
      )}

      {/* News section */}
      {selectedSymbol && (
        <div className="mobile-news-section" ref={newsRef}>
          <NewsCategoryPanel
            symbol={selectedSymbol}
            activeCategory={activeCategory}
            onCategoryChange={handleCategoryChange}
          />
          <NewsPanel
            symbol={selectedSymbol}
            hoveredDate={hoveredDate}
            highlightedNewsId={null}
            isLocked={false}
            onUnlock={() => {}}
            highlightedCategoryIds={activeCategoryIds.length > 0 ? activeCategoryIds : undefined}
          />
        </div>
      )}

      {/* Bottom sheet for similar days */}
      {selectedDay && selectedSymbol && (
        <BottomSheet
          title={t('sim.title', lang)}
          onClose={() => setSelectedDay(null)}
        >
          <SimilarDaysPanel
            symbol={selectedSymbol}
            date={selectedDay}
            onClose={() => setSelectedDay(null)}
          />
        </BottomSheet>
      )}
    </div>
  );
}
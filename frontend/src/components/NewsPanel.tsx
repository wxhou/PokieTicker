import { useState, useEffect, useRef, useMemo } from 'react';
import axios from 'axios';
import { useLang } from '../LanguageContext';
import { t } from '../i18n';

interface NewsItem {
  news_id: string;
  trade_date: string;
  published_utc: string;
  title: string;
  description: string;
  publisher: string;
  article_url: string;
  image_url: string | null;
  relevance: string | null;
  key_discussion: string | null;
  sentiment: string | null;
  reason_growth: string | null;
  reason_decrease: string | null;
  ret_t0: number | null;
  ret_t1: number | null;
  ret_t3: number | null;
  ret_t5: number | null;
  ret_t10: number | null;
}

interface Props {
  symbol: string;
  hoveredDate: string | null;
  onFindSimilar?: (newsId: string) => void;
  highlightedNewsId?: string | null;
  isLocked?: boolean;
  onUnlock?: () => void;
  highlightedCategoryIds?: string[];
}

function sortBySentiment(items: NewsItem[]): NewsItem[] {
  const order: Record<string, number> = { positive: 0, negative: 1, neutral: 2 };
  return [...items].sort((a, b) => {
    const sa = order[a.sentiment || 'neutral'] ?? 2;
    const sb = order[b.sentiment || 'neutral'] ?? 2;
    return sa - sb;
  });
}

interface NewsGroup {
  primary: NewsItem;
  duplicates: NewsItem[];
}

function titleSimilarity(a: string, b: string): number {
  if (!a || !b) return 0;
  // Extract meaningful Chinese segments (2+ chars)
  const segsA = new Set(a.match(/[一-鿿]{2,}/g) || []);
  const segsB = new Set(b.match(/[一-鿿]{2,}/g) || []);
  if (segsA.size === 0 || segsB.size === 0) return 0;
  let overlap = 0;
  for (const s of segsA) if (segsB.has(s)) overlap++;
  return overlap / Math.min(segsA.size, segsB.size);
}

function groupSimilarNews(items: NewsItem[]): NewsGroup[] {
  const used = new Set<string>();
  const groups: NewsGroup[] = [];
  for (const item of items) {
    if (used.has(item.news_id)) continue;
    const group: NewsGroup = { primary: item, duplicates: [] };
    used.add(item.news_id);
    for (const other of items) {
      if (used.has(other.news_id)) continue;
      const sim = titleSimilarity(item.title, other.title);
      // Also check key_discussion overlap for same-event detection
      const discSim = (item.key_discussion && other.key_discussion)
        ? titleSimilarity(item.key_discussion, other.key_discussion) : 0;
      if (sim >= 0.5 || discSim >= 0.7) {
        group.duplicates.push(other);
        used.add(other.news_id);
      }
    }
    groups.push(group);
  }
  return groups;
}

function pct(v: number | null) {
  if (v === null || v === undefined) return '-';
  const pctVal = v * 100;
  const color = pctVal > 0 ? '#e63946' : pctVal < 0 ? '#2d936c' : '#8a8478';
  return <span style={{ color, fontWeight: 600 }}>{pctVal > 0 ? '+' : ''}{pctVal.toFixed(2)}%</span>;
}

export default function NewsPanel({ symbol, hoveredDate, onFindSimilar, highlightedNewsId, isLocked, onUnlock, highlightedCategoryIds }: Props) {
  const { lang } = useLang();
  const [news, setNews] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [displayDate, setDisplayDate] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const cacheRef = useRef<Map<string, NewsItem[]>>(new Map());
  const listRef = useRef<HTMLDivElement>(null);

  // Debounced fetch on hover
  useEffect(() => {
    if (!symbol || !hoveredDate) return;
    // If locked and date hasn't changed, skip refetch
    if (isLocked && displayDate === hoveredDate) return;

    if (debounceRef.current) clearTimeout(debounceRef.current);

    debounceRef.current = setTimeout(() => {
      const cacheKey = `${symbol}_${hoveredDate}`;
      const cached = cacheRef.current.get(cacheKey);
      if (cached) {
        setNews(sortBySentiment(cached));
        setDisplayDate(hoveredDate);
        return;
      }

      setLoading(true);
      axios
        .get(`/api/news/${symbol}?date=${hoveredDate}`)
        .then((res) => {
          cacheRef.current.set(cacheKey, res.data);
          setNews(sortBySentiment(res.data));
          setDisplayDate(hoveredDate);
        })
        .catch(() => {
          setNews([]);
          setDisplayDate(hoveredDate);
        })
        .finally(() => setLoading(false));
    }, 120);
  }, [symbol, hoveredDate]);

  // Load latest news on symbol change
  useEffect(() => {
    cacheRef.current.clear();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setNews([]);
    setDisplayDate(null);

    // Fetch recent news, then filter to the latest trade_date
    axios
      .get(`/api/news/${symbol}`)
      .then((res) => {
        if (res.data && res.data.length > 0) {
          const latestDate = res.data[0].trade_date;
          const latestNews = res.data.filter((n: NewsItem) => n.trade_date === latestDate);
          const cacheKey = `${symbol}_${latestDate}`;
          cacheRef.current.set(cacheKey, latestNews);
          setNews(sortBySentiment(latestNews));
          setDisplayDate(latestDate);
        }
      })
      .catch(console.error);
  }, [symbol]);

  // Auto-scroll to highlighted article
  useEffect(() => {
    if (!highlightedNewsId || !listRef.current) return;
    const el = listRef.current.querySelector(`[data-news-id="${highlightedNewsId}"]`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [highlightedNewsId, news]);

  const categorySet = highlightedCategoryIds && highlightedCategoryIds.length > 0
    ? new Set(highlightedCategoryIds)
    : null;

  // If category filter is active but NO articles on this date match, disable dimming
  const hasAnyMatch = categorySet != null && news.some((item) => categorySet.has(item.news_id));
  const effectiveCategorySet = (categorySet != null && !hasAnyMatch) ? null : categorySet;

  const newsGroups = useMemo(() => groupSimilarNews(news), [news]);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());

  function toggleGroup(newsId: string) {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(newsId)) next.delete(newsId);
      else next.add(newsId);
      return next;
    });
  }

  if (!displayDate) {
    return (
      <div className="news-panel">
        <div className="news-panel-header">
          <h2>{t('news.title', lang)}</h2>
        </div>
        <div className="news-empty">{t('news.clickChart', lang)}</div>
      </div>
    );
  }

  return (
    <div className="news-panel">
      <div className="news-panel-header">
        <h2>{t('news.title', lang)}</h2>
        <span className="news-date-badge">{displayDate}</span>
        <span className="news-count">{news.length}{t('news.articleCount', lang)}</span>
        {isLocked && (
          <button className="lock-badge" onClick={onUnlock} title={t('news.clickUnlock', lang)}>
            {t('news.locked', lang)}
          </button>
        )}
      </div>

      {loading && news.length === 0 ? (
        <div className="news-empty">{t('news.loading', lang)}</div>
      ) : news.length === 0 ? (
        <div className="news-empty">{t('news.noNewsDate', lang)}</div>
      ) : (
        <div className="news-list" ref={listRef}>
          {newsGroups.map((group) => {
            const item = group.primary;
            const isDimmed = effectiveCategorySet != null && !effectiveCategorySet.has(item.news_id);
            const hasDupes = group.duplicates.length > 0;
            const isExpanded = expandedGroups.has(item.news_id);
            return (
              <div key={item.news_id} className="news-group">
                <div
                  data-news-id={item.news_id}
                  className={`news-card ${item.sentiment === 'positive' ? 'card-positive' : item.sentiment === 'negative' ? 'card-negative' : 'card-neutral'}${highlightedNewsId === item.news_id ? ' card-highlighted' : ''}${isDimmed ? ' card-dimmed' : ''}`}
                >
                  <div className="news-card-top">
                    <span className={`sentiment-dot ${item.sentiment || 'neutral'}`} />
                    <a href={item.article_url} target="_blank" rel="noreferrer" className="news-title">
                      {item.title}
                    </a>
                  </div>

                  {item.image_url && (
                    <div className="news-image-wrap">
                      <img
                        src={item.image_url}
                        alt=""
                        className="news-image"
                        loading="lazy"
                        onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                      />
                    </div>
                  )}

                  {item.key_discussion && (
                    <p className="news-summary">{item.key_discussion}</p>
                  )}

                  {(item.reason_growth || item.reason_decrease) && (
                    <div className="news-reasons">
                      {item.reason_growth && (
                        <div className="reason up">
                          <span className="reason-icon">+</span> {item.reason_growth}
                        </div>
                      )}
                      {item.reason_decrease && (
                        <div className="reason down">
                          <span className="reason-icon">-</span> {item.reason_decrease}
                        </div>
                      )}
                    </div>
                  )}

                  <div className="news-card-footer">
                    <span className="news-publisher">{item.publisher}</span>
                    <div className="returns-chips">
                      {item.ret_t1 != null && <span className="ret-chip">T+1 {pct(item.ret_t1)}</span>}
                      {item.ret_t5 != null && <span className="ret-chip">T+5 {pct(item.ret_t5)}</span>}
                      {hasDupes && (
                        <button
                          className="dedup-toggle"
                          onClick={(e) => { e.stopPropagation(); toggleGroup(item.news_id); }}
                        >
                          {isExpanded ? '收起' : `${group.duplicates.length}${t('news.relatedCount', lang)}`}
                        </button>
                      )}
                      {onFindSimilar && (
                        <button
                          className="find-similar-btn"
                          onClick={(e) => { e.stopPropagation(); onFindSimilar(item.news_id); }}
                        >
                          {t('news.similarNews', lang)}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
                {hasDupes && isExpanded && (
                  <div className="dedup-list">
                    {group.duplicates.map((dupe) => (
                      <div key={dupe.news_id} className="dedup-card">
                        <a href={dupe.article_url} target="_blank" rel="noreferrer" className="dedup-title">
                          {dupe.title}
                        </a>
                        <span className="dedup-publisher">{dupe.publisher}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useLang } from '../../LanguageContext';
import { t } from '../../i18n';

interface AttributionReason {
  news_id: string;
  title: string;
  sentiment: string | null;
  source_type: string | null;
  key_discussion: string | null;
}

interface AttributionData {
  symbol: string;
  date: string;
  price_change_pct: number | null;
  reasons: AttributionReason[];
}

const SOURCE_LABELS: Record<string, Record<string, string>> = {
  flash: { zh: '快讯', en: 'Flash' },
  notice: { zh: '公告', en: 'Notice' },
  news: { zh: '新闻', en: 'News' },
  policy: { zh: '政策', en: 'Policy' },
};

function IconArrowUp() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
      <polyline points="16 7 22 7 22 13" />
    </svg>
  );
}

function IconArrowDown() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="22 17 13.5 8.5 8.5 13.5 2 7" />
      <polyline points="16 17 22 17 22 11" />
    </svg>
  );
}

function IconMinus() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}

function getSentimentIcon(s: string | null) {
  if (s === 'positive') return <IconArrowUp />;
  if (s === 'negative') return <IconArrowDown />;
  return <IconMinus />;
}

function sentimentClass(s: string | null): string {
  if (s === 'positive') return 'attr-positive';
  if (s === 'negative') return 'attr-negative';
  return 'attr-neutral';
}

type ConfidenceLevel = 'high' | 'medium' | 'low';

function confidenceLevel(reasonCount: number): ConfidenceLevel {
  if (reasonCount >= 5) return 'high';
  if (reasonCount >= 3) return 'medium';
  return 'low';
}

function confidenceLabel(level: ConfidenceLevel, lang: 'zh' | 'en'): string {
  const labels: Record<ConfidenceLevel, Record<'zh' | 'en', string>> = {
    high:   { zh: '信号强', en: 'Strong signal' },
    medium: { zh: '中等信号', en: 'Moderate signal' },
    low:    { zh: '信号弱', en: 'Weak signal' },
  };
  return labels[level][lang];
}

export default function AttributionCard({ symbol, newsRef }: { symbol: string; newsRef?: React.RefObject<HTMLDivElement | null> }) {
  const { lang } = useLang();
  const [data, setData] = useState<AttributionData | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchAttribution = useCallback(() => {
    if (!symbol) return;
    setLoading(true);
    axios
      .get(`/api/news/${encodeURIComponent(symbol)}/attribution`)
      .then((res) => setData(res.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [symbol]);

  useEffect(() => {
    fetchAttribution();
  }, [fetchAttribution]);

  if (loading) {
    return (
      <div className="attribution-card attribution-skeleton">
        <div className="attr-skeleton-header">
          <div className="attr-skeleton-badge" />
          <div className="attr-skeleton-change" />
        </div>
        <div className="attr-skeleton-reasons">
          <div className="attr-skeleton-reason">
            <div className="attr-skeleton-icon" />
            <div className="attr-skeleton-content">
              <div className="attr-skeleton-title" />
              <div className="attr-skeleton-badge-sm" />
            </div>
          </div>
          <div className="attr-skeleton-reason">
            <div className="attr-skeleton-icon" />
            <div className="attr-skeleton-content">
              <div className="attr-skeleton-title short" />
              <div className="attr-skeleton-badge-sm" />
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!data || data.reasons.length === 0) {
    return (
      <div className="attribution-card attribution-empty">
        <span>{t('mobile.noData', lang)}</span>
      </div>
    );
  }

  return (
    <div className="attribution-card">
      <div className="attr-header">
        <span className="attr-title">{t('mobile.whyMove', lang)}</span>
        <span
          className={`attr-confidence attr-confidence-${confidenceLevel(data.reasons.length)}`}
        >
          {confidenceLabel(confidenceLevel(data.reasons.length), lang)}
        </span>
        {data.price_change_pct != null && (
          <span className={`attr-change ${data.price_change_pct >= 0 ? 'up' : 'down'}`}>
            {data.price_change_pct >= 0 ? '+' : ''}{data.price_change_pct.toFixed(2)}%
          </span>
        )}
      </div>
      <div className="attr-reasons">
        {data.reasons.slice(0, 3).map((r) => (
          <div
            key={r.news_id}
            className={`attr-reason ${sentimentClass(r.sentiment)}`}
            onClick={() => {
              if (newsRef?.current) {
                newsRef.current.scrollIntoView({ behavior: 'smooth' });
              }
            }}
          >
            <span className="attr-reason-icon">{getSentimentIcon(r.sentiment)}</span>
            <div className="attr-reason-content">
              <span className="attr-reason-title">{r.title}</span>
              {r.source_type && (
                <span className="attr-reason-badge">
                  {SOURCE_LABELS[r.source_type]?.[lang] ?? r.source_type}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
      <div className="attr-source">
        {lang === 'zh'
          ? `基于最近 ${data.reasons.length} 条相关新闻`
          : `Based on ${data.reasons.length} recent news article${data.reasons.length === 1 ? '' : 's'}`}
      </div>
    </div>
  );
}
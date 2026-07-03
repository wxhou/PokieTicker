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
  contradiction?: boolean;
  ret_t1?: number | null;
}

interface AiSummary {
  summary: string;
  model?: string;
  cached?: boolean;
}

interface AttributionData {
  symbol: string;
  date: string;
  price_change_pct: number | null;
  reasons: AttributionReason[];
  ai_summary?: AiSummary;
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

function IconWarning() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

function IconSparkle() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2l2.39 7.36L22 12l-7.61 2.64L12 22l-2.39-7.36L2 12l7.61-2.64z" />
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
      {data.ai_summary?.summary && (
        <div className="attr-narrative">
          <div className="attr-narrative-label">
            <IconSparkle />
            <span>{t('mobile.attribution.aiLabel', lang)}</span>
          </div>
          <p className="attr-narrative-text">{data.ai_summary.summary}</p>
        </div>
      )}
      <div className="attr-reasons">
        {data.reasons.slice(0, 3).map((r) => (
          <div
            key={r.news_id}
            className={`attr-reason ${sentimentClass(r.sentiment)}${r.contradiction ? ' attr-reason-contradicts' : ''}`}
            onClick={() => {
              if (newsRef?.current) {
                newsRef.current.scrollIntoView({ behavior: 'smooth' });
              }
            }}
          >
            <span className="attr-reason-icon">{getSentimentIcon(r.sentiment)}</span>
            <div className="attr-reason-content">
              <span className="attr-reason-title">{r.title}</span>
              <div className="attr-reason-meta">
                {r.source_type && (
                  <span className="attr-reason-badge">
                    {SOURCE_LABELS[r.source_type]?.[lang] ?? r.source_type}
                  </span>
                )}
                {r.contradiction && (
                  <span className="attr-reason-warn" title={t('mobile.attribution.contradiction', lang)}>
                    <IconWarning />
                    {t('mobile.attribution.contradiction', lang)}
                  </span>
                )}
              </div>
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
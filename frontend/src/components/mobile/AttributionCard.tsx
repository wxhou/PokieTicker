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

function sentimentIcon(s: string | null): string {
  if (s === 'positive') return '📈';
  if (s === 'negative') return '📉';
  return '📊';
}

function sentimentClass(s: string | null): string {
  if (s === 'positive') return 'attr-positive';
  if (s === 'negative') return 'attr-negative';
  return 'attr-neutral';
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
        <div className="attr-skeleton-line" />
        <div className="attr-skeleton-line short" />
        <div className="attr-skeleton-line" />
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
            <span className="attr-reason-icon">{sentimentIcon(r.sentiment)}</span>
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
    </div>
  );
}
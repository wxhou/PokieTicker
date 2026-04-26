import { useState, useEffect } from 'react';
import axios from 'axios';
import { useLang } from '../LanguageContext';
import { t } from '../i18n';

interface CategoryInfo {
  label: string;
  count: number;
  article_ids: string[];
  positive_ids: string[];
  negative_ids: string[];
  neutral_ids: string[];
}

interface CategoriesResponse {
  categories: Record<string, CategoryInfo>;
  total: number;
}

interface Props {
  symbol: string;
  activeCategory: string | null;
  onCategoryChange: (category: string | null, articleIds: string[], color?: string) => void;
}

const CATEGORY_META: Record<string, { zh: string; en: string; color: string }> = {
  market:       { zh: '市场',   en: 'Market', color: '#c9a96e' },
  policy:       { zh: '政策',   en: 'Policy', color: '#b08040' },
  earnings:     { zh: '业绩',    en: 'Earnings', color: '#e63946' },
  product_tech: { zh: '产品',    en: 'Product', color: '#a07cdc' },
  competition:  { zh: '竞争',   en: 'Competition', color: '#d97706' },
  management:   { zh: '人事',  en: 'Management', color: '#2d936c' },
};

type SentimentFilter = 'all' | 'positive' | 'negative';

export default function NewsCategoryPanel({ symbol, activeCategory, onCategoryChange }: Props) {
  const { lang } = useLang();
  const [categories, setCategories] = useState<Record<string, CategoryInfo>>({});
  const [sentimentFilter, setSentimentFilter] = useState<SentimentFilter>('all');

  useEffect(() => {
    if (!symbol) return;
    axios
      .get<CategoriesResponse>(`/api/news/${symbol}/categories`)
      .then((res) => setCategories(res.data.categories))
      .catch(() => setCategories({}));
  }, [symbol]);

  useEffect(() => {
    setSentimentFilter('all');
  }, [activeCategory]);

  const keys = Object.keys(categories).filter((k) => categories[k].count > 0);
  if (keys.length === 0) return null;

  function handleSentimentClick(filter: SentimentFilter) {
    if (!activeCategory) return;
    const cat = categories[activeCategory];
    const meta = CATEGORY_META[activeCategory] || { color: '#c9a96e' };
    setSentimentFilter(filter);
    let ids: string[];
    let color: string;
    if (filter === 'positive') {
      ids = cat.positive_ids;
      color = '#e63946';
    } else if (filter === 'negative') {
      ids = cat.negative_ids;
      color = '#2d936c';
    } else {
      ids = cat.article_ids;
      color = meta.color;
    }
    onCategoryChange(activeCategory, ids, color);
  }

  const activeCat = activeCategory ? categories[activeCategory] : null;

  return (
    <div className="news-category-wrap">
      <div className="news-category-bar">
        {keys.map((key) => {
          const cat = categories[key];
          const meta = CATEGORY_META[key] || { zh: key, en: key, color: '#c9a96e' };
          const isActive = activeCategory === key;
          const label = lang === 'zh' ? meta.zh : meta.en;
          return (
            <button
              key={key}
              className={`category-tag ${isActive ? 'category-tag-active' : ''}`}
              style={{
                '--tag-color': meta.color,
              } as React.CSSProperties}
              onClick={() => {
                if (isActive) {
                  onCategoryChange(null, []);
                } else {
                  setSentimentFilter('all');
                  onCategoryChange(key, cat.article_ids, meta.color);
                }
              }}
            >
              <span className="category-tag-dot" style={{ background: meta.color }} />
              <span className="category-tag-label">{label}</span>
              <span className="category-tag-count">{cat.count}</span>
            </button>
          );
        })}
      </div>

      {activeCat && (
        <div className="sentiment-sub-bar">
          <button
            className={`sentiment-sub-btn ${sentimentFilter === 'all' ? 'sentiment-sub-active' : ''}`}
            onClick={() => handleSentimentClick('all')}
          >
            {t('cat.all', lang)} <span className="sentiment-sub-count">{activeCat.count}</span>
          </button>
          <button
            className={`sentiment-sub-btn sentiment-sub-up ${sentimentFilter === 'positive' ? 'sentiment-sub-active' : ''}`}
            onClick={() => handleSentimentClick('positive')}
          >
            {t('cat.positive', lang)} <span className="sentiment-sub-count">{activeCat.positive_ids.length}</span>
          </button>
          <button
            className={`sentiment-sub-btn sentiment-sub-down ${sentimentFilter === 'negative' ? 'sentiment-sub-active' : ''}`}
            onClick={() => handleSentimentClick('negative')}
          >
            {t('cat.negative', lang)} <span className="sentiment-sub-count">{activeCat.negative_ids.length}</span>
          </button>
        </div>
      )}
    </div>
  );
}
import { useState, useEffect } from 'react';
import axios from 'axios';
import { useLang } from '../LanguageContext';
import { t } from '../i18n';

interface Stock {
  symbol: string;
  name: string;
  sentiment?: string | null;
  reason?: string | null;
}

interface Event {
  id: string;
  title: string;
  description?: string;
  event_date: string;
  category: string;
  impact?: string | null;
  source?: string;
  stocks: Stock[];
}

interface Props {
  onSelectSymbol?: (symbol: string) => void;
}

const CATEGORY_LABELS: Record<string, { zh: string; en: string; icon: string }> = {
  notice: { zh: '公告', en: 'Notices', icon: '📋' },
  flash: { zh: '快讯', en: 'Flash', icon: '⚡' },
  policy: { zh: '政策', en: 'Policy', icon: '📜' },
};

function formatDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function formatDisplay(d: Date, lang: string): string {
  const weekdays = lang === 'zh'
    ? ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
    : ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const m = d.getMonth() + 1;
  const day = d.getDate();
  return lang === 'zh'
    ? `${d.getFullYear()}年${m}月${day}日 ${weekdays[d.getDay()]}`
    : `${d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })} ${weekdays[d.getDay()]}`;
}

function getWeekRange(d: Date): { start: Date; end: Date } {
  const day = d.getDay();
  const diffToMon = day === 0 ? -6 : 1 - day;
  const monday = new Date(d);
  monday.setDate(d.getDate() + diffToMon);
  const sunday = new Date(monday);
  sunday.setDate(monday.getDate() + 6);
  return { start: monday, end: sunday };
}

function impactClass(impact?: string | null): string {
  if (impact === 'positive') return 'event-impact-positive';
  if (impact === 'negative') return 'event-impact-negative';
  return 'event-impact-neutral';
}

function impactLabel(impact?: string | null, lang: string = 'zh'): string {
  if (impact === 'positive') return lang === 'zh' ? '利好' : 'Positive';
  if (impact === 'negative') return lang === 'zh' ? '利空' : 'Negative';
  return '';
}

export default function EventCalendar({ onSelectSymbol }: Props) {
  const { lang } = useLang();
  const [currentDate, setCurrentDate] = useState(() => new Date());
  const [viewMode, setViewMode] = useState<'day' | 'week'>('day');
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    const start = viewMode === 'week'
      ? formatDate(getWeekRange(currentDate).start)
      : formatDate(currentDate);
    const end = viewMode === 'week'
      ? formatDate(getWeekRange(currentDate).end)
      : formatDate(currentDate);

    setLoading(true);
    axios
      .get(`/api/events?start=${start}&end=${end}`)
      .then((res) => setEvents(res.data as Event[]))
      .catch(() => setEvents([]))
      .finally(() => setLoading(false));
  }, [currentDate, viewMode]);

  function navigate(offset: number) {
    const d = new Date(currentDate);
    d.setDate(d.getDate() + (viewMode === 'week' ? offset * 7 : offset));
    setCurrentDate(d);
  }

  // Group events by date for week view
  const groupedByDate: Record<string, Event[]> = {};
  for (const evt of events) {
    const key = evt.event_date;
    if (!groupedByDate[key]) groupedByDate[key] = [];
    groupedByDate[key].push(evt);
  }

  // Group by category within a date
  function groupByCategory(evts: Event[]) {
    const groups: Record<string, Event[]> = {};
    for (const e of evts) {
      const cat = e.category || 'notice';
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(e);
    }
    return groups;
  }

  function renderEvent(evt: Event) {
    const isExpanded = expandedId === evt.id;
    const label = CATEGORY_LABELS[evt.category] || CATEGORY_LABELS.notice;

    return (
      <div key={evt.id} className="event-item">
        <div className="event-row" onClick={() => setExpandedId(isExpanded ? null : evt.id)}>
          <span className="event-icon">{label.icon}</span>
          <span className="event-title">{evt.title}</span>
          {evt.impact && (
            <span className={`event-impact ${impactClass(evt.impact)}`}>
              {impactLabel(evt.impact, lang)}
            </span>
          )}
          {evt.stocks.length > 0 && (
            <span className="event-stock-count">{evt.stocks.length}{lang === 'zh' ? '只' : ''}</span>
          )}
        </div>
        {isExpanded && evt.stocks.length > 0 && (
          <div className="event-stocks">
            {evt.stocks.map((s) => (
              <div
                key={s.symbol}
                className="event-stock-row"
                onClick={(e) => {
                  e.stopPropagation();
                  onSelectSymbol?.(s.symbol);
                }}
              >
                <span className="event-stock-name">{s.name}</span>
                <span className="event-stock-code">{s.symbol.replace(/\.(SH|SZ)$/, '')}</span>
                {s.sentiment && (
                  <span className={`event-stock-sentiment ${impactClass(s.sentiment)}`}>
                    {impactLabel(s.sentiment, lang)}
                  </span>
                )}
                {s.reason && (
                  <span className="event-stock-reason">{s.reason}</span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  function renderCategoryGroup(cat: string, evts: Event[]) {
    const label = CATEGORY_LABELS[cat] || CATEGORY_LABELS.notice;
    return (
      <div key={cat} className="event-category-group">
        <div className="event-category-header">
          <span>{label.icon} {lang === 'zh' ? label.zh : label.en}</span>
          <span className="event-category-count">({evts.length})</span>
        </div>
        {evts.map(renderEvent)}
      </div>
    );
  }

  function renderDateEvents(dateStr: string, evts: Event[]) {
    const groups = groupByCategory(evts);
    const d = new Date(dateStr + 'T00:00:00');
    return (
      <div key={dateStr} className="event-date-section">
        {viewMode === 'week' && (
          <div className="event-date-label">{formatDisplay(d, lang)}</div>
        )}
        {Object.entries(groups).map(([cat, items]) => renderCategoryGroup(cat, items))}
      </div>
    );
  }

  const displayDate = viewMode === 'week'
    ? `${formatDisplay(getWeekRange(currentDate).start, lang)} — ${formatDisplay(getWeekRange(currentDate).end, lang)}`
    : formatDisplay(currentDate, lang);

  return (
    <div className="event-calendar">
      <div className="event-calendar-header">
        <button className="event-nav-btn" onClick={() => navigate(-1)}>&#8249;</button>
        <span className="event-calendar-date">{displayDate}</span>
        <button className="event-nav-btn" onClick={() => navigate(1)}>&#8250;</button>
        <div className="event-view-toggle">
          <button
            className={`event-view-btn ${viewMode === 'day' ? 'active' : ''}`}
            onClick={() => setViewMode('day')}
          >
            {lang === 'zh' ? '日' : 'Day'}
          </button>
          <button
            className={`event-view-btn ${viewMode === 'week' ? 'active' : ''}`}
            onClick={() => setViewMode('week')}
          >
            {lang === 'zh' ? '周' : 'Week'}
          </button>
        </div>
      </div>

      <div className="event-calendar-body">
        {loading ? (
          <div className="event-loading">{lang === 'zh' ? '加载中...' : 'Loading...'}</div>
        ) : events.length === 0 ? (
          <div className="event-empty">{lang === 'zh' ? '暂无事件' : 'No events'}</div>
        ) : viewMode === 'week' ? (
          Object.entries(groupedByDate)
            .sort(([a], [b]) => b.localeCompare(a))
            .map(([date, evts]) => renderDateEvents(date, evts))
        ) : (
          renderDateEvents(formatDate(currentDate), events)
        )}
      </div>
    </div>
  );
}

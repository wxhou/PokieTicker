import { useLang } from '../../LanguageContext';
import { t } from '../../i18n';
import type { JSX } from 'react';

export type MobileRoute = 'home' | 'events' | 'portfolio' | 'settings';

interface Props {
  route: MobileRoute;
  onNavigate: (r: MobileRoute) => void;
}

const TABS: { key: MobileRoute; label: string }[] = [
  { key: 'home', label: 'home' },
  { key: 'events', label: 'events' },
  { key: 'portfolio', label: 'portfolio' },
  { key: 'settings', label: 'settings' },
];

function IconHome({ active }: { active: boolean }) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 9.5L12 3l9 6.5V20a1 1 0 01-1 1H4a1 1 0 01-1-1V9.5z" />
      <path d="M9 21V12h6v9" />
      {active && <path d="M12 7.5l3.5 2.5-.5 1L12 9l-3 2-.5-1L12 7.5z" fill="currentColor" stroke="none" />}
    </svg>
  );
}

function IconCalendar({ active }: { active: boolean }) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="18" rx="2" />
      <path d="M16 2v4M8 2v4M3 10h18" />
      <path d="M8 14h.01M12 14h.01M16 14h.01M8 17h.01M12 17h.01" strokeWidth="2" />
      {active && <path d="M9 14h.01M13 14h.01" strokeWidth="2" stroke="currentColor" />}
    </svg>
  );
}

function IconBriefcase({ active }: { active: boolean }) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="7" width="20" height="14" rx="2" />
      <path d="M16 7V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v2" />
      <path d="M12 12v.01" strokeWidth="2" />
      {active && <path d="M12 11v2" strokeWidth="2" />}
    </svg>
  );
}

function IconSettings({ active }: { active: boolean }) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
      {active && <circle cx="12" cy="12" r="1.5" fill="currentColor" stroke="none" />}
    </svg>
  );
}

const ICONS: Record<MobileRoute, (p: { active: boolean }) => JSX.Element> = {
  home: IconHome,
  events: IconCalendar,
  portfolio: IconBriefcase,
  settings: IconSettings,
};

export default function MobileBottomNav({ route, onNavigate }: Props) {
  const { lang } = useLang();

  const labelMap: Record<MobileRoute, string> = {
    home: t('mobile.home', lang),
    events: t('mobile.events', lang),
    portfolio: t('mobile.portfolio', lang),
    settings: t('mobile.settings', lang),
  };

  return (
    <nav className="mobile-bottom-nav">
      {TABS.map((tab) => {
        const isActive = route === tab.key;
        const Icon = ICONS[tab.key];
        return (
          <button
            key={tab.key}
            className={`mobile-nav-tab ${isActive ? 'active' : ''}`}
            onClick={() => onNavigate(tab.key)}
          >
            <span className="mobile-nav-icon">
              <Icon active={isActive} />
            </span>
            <span className="mobile-nav-label">{labelMap[tab.key]}</span>
          </button>
        );
      })}
    </nav>
  );
}
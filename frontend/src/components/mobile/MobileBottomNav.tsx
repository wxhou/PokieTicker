import { useLang } from '../../LanguageContext';
import { t } from '../../i18n';

export type MobileRoute = 'home' | 'events' | 'portfolio' | 'settings';

interface Props {
  route: MobileRoute;
  onNavigate: (r: MobileRoute) => void;
}

const TABS: { key: MobileRoute; icon: string }[] = [
  { key: 'home', icon: '🏠' },
  { key: 'events', icon: '📅' },
  { key: 'portfolio', icon: '💼' },
  { key: 'settings', icon: '⚙️' },
];

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
      {TABS.map((tab) => (
        <button
          key={tab.key}
          className={`mobile-nav-tab ${route === tab.key ? 'active' : ''}`}
          onClick={() => onNavigate(tab.key)}
        >
          <span className="mobile-nav-icon">{tab.icon}</span>
          <span className="mobile-nav-label">{labelMap[tab.key]}</span>
        </button>
      ))}
    </nav>
  );
}
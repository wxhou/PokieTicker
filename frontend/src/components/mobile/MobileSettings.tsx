import { useLang } from '../../LanguageContext';
import { t } from '../../i18n';

function IconMoon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" />
    </svg>
  );
}

function IconSun() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="5" />
      <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
    </svg>
  );
}

function IconWater() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2.69l5.66 5.66a8 8 0 11-11.31 0z" />
    </svg>
  );
}

const THEME_ICONS = {
  obsidian: IconMoon,
  parchment: IconSun,
  azure: IconWater,
};

const THEME_LABELS = { obsidian: '暗', parchment: '亮', azure: '蓝' };

export default function MobileSettings() {
  const { lang, setLang, isZh, theme, setTheme } = useLang();

  return (
    <div className="mobile-settings">
      <div className="mobile-settings-group">
        <div className="mobile-settings-label">{isZh ? '外观' : 'Appearance'}</div>
        <div className="mobile-settings-row">
          <span>{isZh ? '主题' : 'Theme'}</span>
          <div className="mobile-settings-options">
            {(Object.keys(THEME_ICONS) as Array<keyof typeof THEME_ICONS>).map((th) => {
              const Icon = THEME_ICONS[th];
              return (
                <button
                  key={th}
                  className={`mobile-settings-opt ${theme === th ? 'active' : ''}`}
                  onClick={() => setTheme(th)}
                >
                  <Icon />
                  <span className="opt-label">{THEME_LABELS[th]}</span>
                </button>
              );
            })}
          </div>
        </div>
        <div className="mobile-settings-row">
          <span>{isZh ? '语言' : 'Language'}</span>
          <div className="mobile-settings-options">
            <button
              className={`mobile-settings-opt ${isZh ? 'active' : ''}`}
              onClick={() => setLang('zh')}
            >
              中文
            </button>
            <button
              className={`mobile-settings-opt ${!isZh ? 'active' : ''}`}
              onClick={() => setLang('en')}
            >
              EN
            </button>
          </div>
        </div>
      </div>
      <div className="mobile-settings-group">
        <div className="mobile-settings-label">{isZh ? '关于' : 'About'}</div>
        <div className="mobile-settings-about">
          <p>涨讯 · A股因果归因引擎</p>
          <p>{t('footer.disclaimer', lang)}</p>
        </div>
      </div>
    </div>
  );
}
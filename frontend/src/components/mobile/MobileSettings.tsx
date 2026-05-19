import { useLang } from '../../LanguageContext';
import { t } from '../../i18n';

export default function MobileSettings() {
  const { lang, setLang, isZh, theme, setTheme } = useLang();

  return (
    <div className="mobile-settings">
      <div className="mobile-settings-group">
        <div className="mobile-settings-label">{isZh ? '外观' : 'Appearance'}</div>
        <div className="mobile-settings-row">
          <span>{isZh ? '主题' : 'Theme'}</span>
          <div className="mobile-settings-options">
            {(['obsidian', 'parchment', 'azure'] as const).map((th) => (
              <button
                key={th}
                className={`mobile-settings-opt ${theme === th ? 'active' : ''}`}
                onClick={() => setTheme(th)}
              >
                {th === 'obsidian' ? '🌙' : th === 'parchment' ? '☀️' : '🌊'}
              </button>
            ))}
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
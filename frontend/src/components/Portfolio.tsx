import { useState, useEffect } from 'react';
import axios from 'axios';
import ScreenshotImport from './ScreenshotImport';
import { useLang } from '../LanguageContext';
import { t } from '../i18n';

interface Holding {
  id: number;
  stock_code: string;
  added_at: string;
  source?: string;
  close?: number;
  pct_chg?: number;
}

interface Portfolio {
  id: number;
  name: string;
  created_at: string;
  holdings: Holding[];
}

function extractError(e: unknown, fallback: string): string {
  const d = (e as { response?: { data?: { detail?: string } | { msg?: string }[] } })?.response?.data;
  if (Array.isArray(d) && d.length > 0) return (d[0] as { msg?: string }).msg || fallback;
  if (typeof (d as { detail?: string })?.detail === 'string') return (d as { detail: string }).detail;
  return fallback;
}

interface Props {
  onBack: () => void;
}

export default function Portfolio({ onBack }: Props) {
  const { lang } = useLang();
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState<string | null>(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [authError, setAuthError] = useState('');
  const [showLogin, setShowLogin] = useState(false);
  const [newName, setNewName] = useState('');
  const [addCode, setAddCode] = useState<Record<number, string>>({});
  const [error, setError] = useState('');
  const [showScreenshot, setShowScreenshot] = useState(false);

  async function loadPortfolios(tk: string) {
    setLoading(true);
    try {
      const res = await axios.get('/api/portfolio', {
        headers: { Authorization: `Bearer ${tk}` },
      });
      setPortfolios(res.data);
    } catch (e: unknown) {
      if ((e as { response?: { status?: number } })?.response?.status === 401) {
        localStorage.removeItem('zx_auth_token');
        setToken(null);
        setShowLogin(true);
      } else {
        setError(t('portfolio.loadFail', lang));
      }
    }
    setLoading(false);
  }

  useEffect(() => {
    const savedToken = localStorage.getItem('zx_auth_token');
    if (savedToken) {
      setToken(savedToken);
      loadPortfolios(savedToken);
    } else {
      setShowLogin(true);
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setAuthError('');
    try {
      const res = await axios.post('/api/auth/login', { email, password });
      const tk = res.data.access_token;
      localStorage.setItem('zx_auth_token', tk);
      setToken(tk);
      setShowLogin(false);
      loadPortfolios(tk);
    } catch (e: unknown) {
      setAuthError(extractError(e, t('portfolio.loginFail', lang)));
    }
  }

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault();
    setAuthError('');
    try {
      await axios.post('/api/auth/register', { email, password });
      await handleLogin(e);
    } catch (e: unknown) {
      setAuthError(extractError(e, t('portfolio.signUpFail', lang)));
    }
  }

  async function handleLogout() {
    localStorage.removeItem('zx_auth_token');
    setToken(null);
    setPortfolios([]);
    setShowLogin(true);
  }

  async function createPortfolio() {
    if (!newName.trim() || !token) return;
    try {
      const res = await axios.post('/api/portfolio', { name: newName.trim() }, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setPortfolios([res.data, ...portfolios]);
      setNewName('');
    } catch (e: unknown) {
      setError(extractError(e, t('portfolio.createFail', lang)));
    }
  }

  async function deletePortfolio(id: number) {
    if (!token) return;
    try {
      await axios.delete(`/api/portfolio/${id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setPortfolios(portfolios.filter(p => p.id !== id));
    } catch (e: unknown) {
      setError(extractError(e, t('portfolio.deleteFail', lang)));
    }
  }

  async function addHolding(portfolioId: number) {
    const code = addCode[portfolioId]?.trim().toUpperCase();
    if (!code || !token) return;
    try {
      await axios.post('/api/portfolio/holdings', { portfolio_id: portfolioId, stock_code: code }, {
        headers: { Authorization: `Bearer ${token}` },
      });
      loadPortfolios(token);
      setAddCode(prev => ({ ...prev, [portfolioId]: '' }));
    } catch (e: unknown) {
      setError(extractError(e, t('portfolio.addFail', lang)));
    }
  }

  async function removeHolding(holdingId: number) {
    if (!token) return;
    try {
      await axios.delete(`/api/portfolio/holdings/${holdingId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setPortfolios(portfolios.map(p => ({
        ...p,
        holdings: p.holdings.filter(h => h.id !== holdingId),
      })));
    } catch (e: unknown) {
      setError(extractError(e, t('portfolio.removeFail', lang)));
    }
  }

  if (loading) {
    return (
      <div className="portfolio-loading">
        <div className="range-spinner" />
        <span>{t('news.loading', lang)}</span>
      </div>
    );
  }

  if (showLogin || !token) {
    return (
      <div className="portfolio-auth">
        <div className="portfolio-auth-card">
          <h2>{t('portfolio.loginTitle', lang)}</h2>
          <p className="portfolio-auth-sub">{t('portfolio.loginSub', lang)}</p>
          {authError && <div className="auth-error">{authError}</div>}
          <form onSubmit={handleLogin}>
            <div className="form-group">
              <label>{t('portfolio.email', lang)}</label>
              <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="your@email.com" required />
            </div>
            <div className="form-group">
              <label>{t('portfolio.password', lang)}</label>
              <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" required />
            </div>
            <div className="auth-actions">
              <button type="submit" className="btn-primary">{t('portfolio.signIn', lang)}</button>
              <button type="button" className="btn-secondary" onClick={handleRegister}>{t('portfolio.signUp', lang)}</button>
            </div>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="portfolio-page">
      <div className="portfolio-header">
        <h2>{t('portfolio.title', lang)}</h2>
        <button className="btn-ghost" onClick={() => setShowScreenshot(true)}>{t('portfolio.screenshotImport', lang)}</button>
        <button className="btn-ghost" onClick={onBack}>{t('nav.back', lang)}</button>
        <button className="btn-ghost btn-danger" onClick={handleLogout}>{t('portfolio.signOut', lang)}</button>
      </div>

      {error && <div className="portfolio-error">{error}</div>}

      <div className="portfolio-create">
        <input
          type="text"
          value={newName}
          onChange={e => setNewName(e.target.value)}
          placeholder={t('portfolio.createPlaceholder', lang)}
          onKeyDown={e => e.key === 'Enter' && createPortfolio()}
        />
        <button className="btn-primary" onClick={createPortfolio}>{t('portfolio.create', lang)}</button>
      </div>

      {portfolios.length === 0 ? (
        <div className="portfolio-empty">
          <p>{t('portfolio.empty', lang)}</p>
          <p className="portfolio-empty-hint">{t('portfolio.addHint2', lang)}</p>
        </div>
      ) : (
        <div className="portfolio-list">
          {portfolios.map(p => (
            <div key={p.id} className="portfolio-card">
              <div className="portfolio-card-header">
                <h3>{p.name}</h3>
                <span className="portfolio-card-meta">{p.holdings.length}{t('portfolio.holdingsCount', lang)}</span>
                <button className="btn-icon danger" onClick={() => deletePortfolio(p.id)} title={t('portfolio.deletePortfolio', lang)}>✕</button>
              </div>
              <div className="portfolio-holdings">
                {p.holdings.map(h => (
                  <div key={h.id} className="holding-item">
                    <span className="holding-code">{h.stock_code}</span>
                    {h.source && (
                      <span className={`source-badge ${h.source === 'screenshot' ? 'screenshot' : 'manual'}`}>
                        {h.source === 'screenshot' ? t('portfolio.screenshot', lang) : t('portfolio.manual', lang)}
                      </span>
                    )}
                    {h.close != null && (
                      <span className={`holding-change ${(h.pct_chg || 0) >= 0 ? 'up' : 'down'}`}>
                        {h.close.toFixed(2)}
                        {(h.pct_chg || 0) >= 0 ? '+' : ''}{((h.pct_chg || 0)).toFixed(2)}%
                      </span>
                    )}
                    <button className="btn-icon" onClick={() => removeHolding(h.id)} title={t('portfolio.remove', lang)}>✕</button>
                  </div>
                ))}
              </div>
              {p.holdings.length < 10 && (
                <div className="portfolio-add-holding">
                  <input
                    type="text"
                    value={addCode[p.id] || ''}
                    onChange={e => setAddCode(prev => ({ ...prev, [p.id]: e.target.value }))}
                    placeholder={t('portfolio.addCodePlaceholder', lang)}
                    onKeyDown={e => e.key === 'Enter' && addHolding(p.id)}
                  />
                  <button className="btn-add" onClick={() => addHolding(p.id)}>+</button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      {showScreenshot && token && (
        <ScreenshotImport
          token={token}
          onSuccess={() => loadPortfolios(token)}
          onClose={() => setShowScreenshot(false)}
        />
      )}
    </div>
  );
}
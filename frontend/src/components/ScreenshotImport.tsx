import { useState, useRef, useCallback } from 'react';
import axios from 'axios';
import { useLang } from '../LanguageContext';
import { t } from '../i18n';

interface Holding {
  stock_code: string;
  stock_name: string;
  quantity: null | number;
  source: string;
  confidence: number;
  in_database: boolean;
}

interface Props {
  token: string;
  onSuccess: () => void;
  onClose: () => void;
}

export default function ScreenshotImport({ token, onSuccess, onClose }: Props) {
  const { lang } = useLang();
  const [phase, setPhase] = useState<'idle' | 'preview' | 'parsing' | 'results' | 'empty' | 'error'>('idle');
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [errorMsg, setErrorMsg] = useState('');
  const [toast, setToast] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dropRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const handleFileChange = useCallback((f: File) => {
    const allowed = ['image/jpeg', 'image/png', 'image/webp'];
    if (!allowed.includes(f.type)) {
      setErrorMsg(t('si.invalidFormat', lang));
      return;
    }
    if (f.size > 10 * 1024 * 1024) {
      setErrorMsg(t('si.fileTooLarge', lang));
      return;
    }
    setErrorMsg('');
    setFile(f);
    const url = URL.createObjectURL(f);
    setPreviewUrl(url);
    setPhase('preview');
  }, [lang]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const f = e.dataTransfer.files[0];
    if (f) handleFileChange(f);
  }, [handleFileChange]);

  const handleRetake = () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setFile(null);
    setPreviewUrl(null);
    setHoldings([]);
    setSelected(new Set());
    setErrorMsg('');
    setPhase('idle');
  };

  const handleUpload = async () => {
    if (!file) return;
    setPhase('parsing');
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await axios.post('/api/portfolio/screenshot', form, {
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'multipart/form-data' },
      });
      const data = res.data as { holdings: Holding[]; unidentified: number; message: string };
      if (data.holdings.length === 0) {
        setHoldings([]);
        setPhase('empty');
      } else {
        setHoldings(data.holdings);
        setSelected(new Set(data.holdings.map(h => h.stock_code)));
        setPhase('results');
      }
    } catch (e: unknown) {
      const status = (e as { response?: { status?: number } })?.response?.status;
      if (status === 422) setErrorMsg(t('si.invalidFormat', lang));
      else if (status === 413) setErrorMsg(t('si.fileTooLarge', lang));
      else setErrorMsg(t('si.aiUnavailable', lang));
      setPhase('error');
    }
  };

  const handleConfirm = async () => {
    if (selected.size === 0) return;
    setPhase('parsing');
    try {
      const res = await axios.post('/api/portfolio/import', {
        stock_codes: Array.from(selected),
      }, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = res.data as { imported: number; skipped: number; not_found: string[]; message: string };
      if (data.imported > 0 && data.skipped === 0 && data.not_found.length === 0) {
        setToast(t('portfolio.importSuccess', lang));
      } else {
        const parts = [];
        if (data.imported > 0) parts.push(`${t('portfolio.importSuccess', lang)}${data.imported}${t('si.stocks', lang)}`);
        if (data.skipped > 0) parts.push(`${t('news.collapse', lang)}${data.skipped}${t('si.stocks', lang)}`);
        if (data.not_found.length > 0) parts.push(`${data.not_found.length}${t('si.stocks', lang)}${lang === 'zh' ? '不存在' : ' not found'}`);
        setToast(parts.join(lang === 'zh' ? '，' : ', '));
      }
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => setToast(''), 3000);
      onSuccess();
      onClose();
    } catch {
      setToast(t('portfolio.importFail', lang));
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => setToast(''), 5000);
      setPhase('results');
    }
  };

  const toggleStock = (code: string) => {
    const next = new Set(selected);
    if (next.has(code)) next.delete(code);
    else next.add(code);
    setSelected(next);
  };

  return (
    <>
      <style>{`
        .si-overlay {
          position: fixed; inset: 0; z-index: 900;
          background: rgba(0, 0, 0, 0.7);
          display: flex; align-items: center; justify-content: center;
          padding: 16px;
        }
        .si-modal {
          background: var(--bg-surface, #191714);
          border: 1px solid #2a2a3a;
          border-radius: 12px;
          width: 100%; max-width: 448px;
          padding: 20px;
          position: relative;
          animation: siSlideIn 0.2s ease;
        }
        @keyframes siSlideIn {
          from { transform: translateY(20px); opacity: 0; }
          to { transform: translateY(0); opacity: 1; }
        }
        .si-header {
          display: flex; align-items: center; justify-content: space-between;
          margin-bottom: 16px;
        }
        .si-title {
          font-size: 16px; font-weight: 700; color: #fff;
        }
        .si-close {
          width: 28px; height: 28px;
          background: transparent; border: 1px solid var(--border, #3a3630);
          border-radius: 6px; color: var(--text-secondary, #8a8478); font-size: 16px;
          cursor: pointer; display: flex; align-items: center; justify-content: center;
          transition: all 0.15s;
        }
        .si-close:hover { border-color: var(--accent-gold, #c9a96e); color: var(--accent-gold, #c9a96e); }

        /* Drop zone */
        .si-drop {
          border: 1.5px dashed var(--border, #3a3630);
          border-radius: 10px;
          padding: 28px 16px;
          text-align: center;
          cursor: pointer;
          transition: all 0.2s;
          animation: siPulse 3s ease-in-out infinite;
        }
        .si-drop:hover, .si-drop.drag-over {
          border-color: var(--accent-gold, #c9a96e);
          background: rgba(102, 126, 234, 0.05);
          animation-play-state: paused;
        }
        @keyframes siPulse {
          0%, 100% { border-color: var(--border, #3a3630); }
          50% { border-color: var(--accent-gold-muted, #a08850); }
        }
        .si-drop-icon {
          font-size: 32px; margin-bottom: 8px;
          animation: siFloat 2s ease-in-out infinite;
        }
        @keyframes siFloat {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-4px); }
        }
        .si-drop-text {
          font-size: 14px; color: var(--text-secondary, #8a8478); margin-bottom: 12px;
        }
        .si-drop-hint {
          font-size: 12px; color: var(--text-muted, #5c5750); margin-bottom: 16px;
        }
        .si-drop-btns {
          display: flex; gap: 8px; justify-content: center;
        }
        .si-drop-btn {
          padding: 7px 16px;
          border: 1px solid var(--border, #3a3630);
          background: transparent;
          border-radius: 6px;
          color: var(--text-secondary, #8a8478); font-size: 13px; font-weight: 600;
          cursor: pointer; font-family: inherit;
          transition: all 0.15s;
        }
        .si-drop-btn:hover { border-color: var(--accent-gold, #c9a96e); color: var(--accent-gold, #c9a96e); }
        .si-drop-btn.primary {
          background: var(--accent-gold, #c9a96e); border-color: var(--accent-gold, #c9a96e); color: #fff;
        }
        .si-drop-btn.primary:hover { background: var(--accent-gold-muted, #a08850); }

        /* Error state on drop zone */
        .si-drop.error { border-color: #f87171; animation: none; }
        .si-error-text { color: #f87171; font-size: 13px; margin-top: 8px; }

        /* Preview */
        .si-preview {
          margin-bottom: 12px; text-align: center;
        }
        .si-preview img {
          max-height: 200px; max-width: 100%; border-radius: 8px;
          border: 1px solid var(--border, #3a3630);
        }
        .si-preview-btns {
          display: flex; gap: 8px; justify-content: center; margin-top: 10px;
        }

        /* Parsing overlay */
        .si-parsing {
          position: relative; margin: 12px 0;
          border-radius: 10px; overflow: hidden;
          border: 1.5px dashed var(--border, #3a3630);
        }
        .si-parsing-bg {
          padding: 32px; text-align: center;
        }
        .si-spinner {
          width: 28px; height: 28px;
          border: 2px solid var(--border, #3a3630);
          border-top-color: var(--accent-gold, #c9a96e);
          border-radius: 50%;
          animation: siSpin 0.7s linear infinite;
          margin: 0 auto 10px;
        }
        @keyframes siSpin { to { transform: rotate(360deg); } }
        .si-parsing-text { font-size: 14px; color: var(--accent-gold, #c9a96e); }

        /* Results */
        .si-results-header {
          font-size: 14px; font-weight: 600; color: #fff;
          margin-bottom: 12px;
        }
        .si-results-count {
          color: var(--accent-gold, #c9a96e); margin-left: 4px;
        }
        .si-list { display: flex; flex-direction: column; gap: 8px; margin-bottom: 16px; }
        .si-row {
          display: flex; align-items: center; gap: 8px;
          background: var(--bg-card, #211f1b); border-radius: 8px; padding: 10px 12px;
        }
        .si-row input[type="checkbox"] { width: 18px; height: 18px; cursor: pointer; }
        .si-row-info { flex: 1; }
        .si-row-name {
          font-size: 14px; font-weight: 600; color: #e0e0e0;
        }
        .si-row-code {
          font-size: 12px; color: var(--text-secondary, #8a8478); font-family: 'SF Mono', 'Fira Code', monospace;
        }
        .source-badge {
          font-size: 11px; font-weight: 500;
          padding: 2px 8px; border-radius: 999px;
          display: inline-block; vertical-align: middle;
        }
        .source-badge.screenshot {
          background: #1e3a5f; color: #60a5fa;
          border: 1px solid #1e3a5f;
        }
        .source-badge.manual {
          background: var(--bg-card, #211f1b); color: var(--text-secondary, #8a8478);
          border: 1px solid var(--border, #3a3630);
        }
        .si-row-disabled {
          opacity: 0.4; cursor: not-allowed;
        }
        .si-row-disabled input { cursor: not-allowed; }
        .si-disabled-reason {
          font-size: 11px; color: #f87171;
        }

        /* Empty state */
        .si-empty {
          text-align: center; padding: 20px;
        }
        .si-empty-icon {
          font-size: 40px; margin-bottom: 12px;
        }
        .si-empty-title {
          font-size: 15px; font-weight: 600; color: #fff; margin-bottom: 6px;
        }
        .si-empty-sub {
          font-size: 13px; color: #666; margin-bottom: 16px;
        }

        /* Error state */
        .si-error-state {
          text-align: center; padding: 20px;
        }
        .si-error-state-icon {
          font-size: 40px; margin-bottom: 12px;
        }
        .si-error-state-msg {
          font-size: 14px; color: var(--text-secondary, #8a8478); margin-bottom: 16px;
        }

        /* Actions */
        .si-actions {
          display: flex; gap: 8px;
        }
        .si-actions .btn-primary { flex: 1; }
        .si-actions .btn-secondary { flex: 1; }

        /* Toast */
        .si-toast {
          position: absolute; top: -40px; left: 0; right: 0;
          text-align: center;
          background: rgba(255, 82, 82, 0.2); border: 1px solid rgba(255, 82, 82, 0.4);
          border-radius: 6px; padding: 8px; color: #ff5252; font-size: 13px;
        }

        /* Mobile bottom sheet */
        @media (max-width: 768px) {
          .si-overlay { align-items: flex-end; padding: 0; }
          .si-modal {
            max-width: 100%; border-radius: 16px 16px 0 0;
            padding: 20px 20px 32px;
          }
        }
      `}</style>

      <div className="si-overlay" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
        <div className="si-modal" role="dialog" aria-modal="true" aria-labelledby="si-title">
          {toast && <div className="si-toast">{toast}</div>}

          <div className="si-header">
            <span className="si-title" id="si-title">{t('si.title', lang)}</span>
            <button className="si-close" onClick={onClose} aria-label={t('si.close', lang)}>✕</button>
          </div>

          {/* Idle / Drop zone */}
          {(phase === 'idle' || phase === 'error') && (
            <div
              ref={dropRef}
              className={`si-drop${errorMsg ? ' error' : ''}`}
              role="button"
              tabIndex={0}
              aria-label={t('si.dragDrop', lang)}
              onClick={() => fileInputRef.current?.click()}
              onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') fileInputRef.current?.click(); }}
              onDragOver={e => { e.preventDefault(); dropRef.current?.classList.add('drag-over'); }}
              onDragLeave={() => dropRef.current?.classList.remove('drag-over')}
              onDrop={handleDrop}
            >
              <div className="si-drop-icon">📷</div>
              <div className="si-drop-text">{t('si.dragDrop', lang)}</div>
              <div className="si-drop-hint">{t('si.supportedFormats', lang)}</div>
              <div className="si-drop-btns">
                <button className="si-drop-btn" onClick={e => { e.stopPropagation(); fileInputRef.current?.click(); }}>
                  {t('si.selectFile', lang)}
                </button>
                <button className="si-drop-btn primary" onClick={e => { e.stopPropagation(); fileInputRef.current?.click(); }} capture="environment">
                  {t('si.takePhoto', lang)}
                </button>
              </div>
              {errorMsg && <div className="si-error-text">{errorMsg}</div>}
              <input
                ref={fileInputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                capture="environment"
                style={{ display: 'none' }}
                onChange={e => { const f = e.target.files?.[0]; if (f) handleFileChange(f); }}
              />
            </div>
          )}

          {/* Preview */}
          {phase === 'preview' && (
            <>
              <div className="si-preview">
                {previewUrl && <img src={previewUrl} alt={t('si.title', lang)} />}
                <div className="si-preview-btns">
                  <button className="si-drop-btn" onClick={handleRetake}>{t('si.retake', lang)}</button>
                  <button className="si-drop-btn primary" onClick={handleUpload}>{t('si.confirmUpload', lang)}</button>
                </div>
              </div>
              <div className="si-parsing">
                <div className="si-parsing-bg">
                  <div className="si-spinner" />
                  <div className="si-parsing-text">{t('si.recognizing', lang)}</div>
                </div>
              </div>
            </>
          )}

          {/* Parsing */}
          {phase === 'parsing' && (
            <div className="si-parsing">
              <div className="si-parsing-bg">
                <div className="si-spinner" />
                <div className="si-parsing-text">{t('si.recognizing', lang)}</div>
              </div>
            </div>
          )}

          {/* Results */}
          {phase === 'results' && (
            <>
              <div className="si-results-header">
                {t('si.results', lang)}（<span className="si-results-count">{holdings.length}</span>{t('si.stocks', lang)}）
              </div>
              <div className="si-list">
                {holdings.map(h => (
                  <div key={h.stock_code} className="si-row">
                    <input
                      type="checkbox"
                      checked={selected.has(h.stock_code)}
                      onChange={() => toggleStock(h.stock_code)}
                      aria-label={`${h.stock_name} ${h.stock_code}`}
                    />
                    <div className="si-row-info">
                      <div className="si-row-name">{h.stock_name}</div>
                      <div className="si-row-code">
                        {h.stock_code}
                        <span className={`source-badge ${h.source === t('portfolio.screenshot', lang) || h.source === 'screenshot' ? 'screenshot' : 'manual'}`}>
                          {h.source === 'screenshot' ? t('portfolio.screenshot', lang) : t('portfolio.manual', lang)}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              <div className="si-actions">
                <button className="btn-primary" onClick={handleConfirm} disabled={selected.size === 0}>
                  {t('si.confirmImport', lang)}{selected.size > 0 ? ` (${selected.size})` : ''}
                </button>
                <button className="btn-secondary" onClick={onClose}>
                  {t('si.cancel', lang)}
                </button>
              </div>
            </>
          )}

          {/* Empty */}
          {phase === 'empty' && (
            <div className="si-empty">
              <div className="si-empty-icon">❌</div>
              <div className="si-empty-title">{t('si.noStocks', lang)}</div>
              <div className="si-empty-sub">{t('si.noStocksHint', lang)}</div>
              <button className="btn-primary" onClick={handleRetake}>{t('si.reUpload', lang)}</button>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
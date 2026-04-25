import { useState, useRef, useCallback } from 'react';
import axios from 'axios';

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
  const [phase, setPhase] = useState<'idle' | 'preview' | 'parsing' | 'results' | 'empty' | 'error'>('idle');
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [errorMsg, setErrorMsg] = useState('');
  const [toast, setToast] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dropRef = useRef<HTMLDivElement>(null);

  const handleFileChange = useCallback((f: File) => {
    const allowed = ['image/jpeg', 'image/png', 'image/webp'];
    if (!allowed.includes(f.type)) {
      setErrorMsg('仅支持 jpg、png、webp 格式');
      return;
    }
    if (f.size > 10 * 1024 * 1024) {
      setErrorMsg('图片不能超过10MB');
      return;
    }
    setErrorMsg('');
    setFile(f);
    const url = URL.createObjectURL(f);
    setPreviewUrl(url);
    setPhase('preview');
  }, []);

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
    } catch (e: any) {
      const status = e.response?.status;
      if (status === 422) setErrorMsg('仅支持 jpg、png、webp 格式');
      else if (status === 413) setErrorMsg('图片不能超过10MB');
      else setErrorMsg('AI 识别服务暂时不可用，请稍后重试');
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
        setToast(`导入成功`);
      } else {
        const parts = [];
        if (data.imported > 0) parts.push(`导入成功${data.imported}只`);
        if (data.skipped > 0) parts.push(`跳过${data.skipped}只`);
        if (data.not_found.length > 0) parts.push(`${data.not_found.length}只不存在`);
        setToast(parts.join('，'));
      }
      setTimeout(() => setToast(''), 3000);
      onSuccess();
      onClose();
    } catch {
      setToast('导入失败，请重试');
      setTimeout(() => setToast(''), 5000);
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
          background: #1a1a24;
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
          background: transparent; border: 1px solid #3a3a4a;
          border-radius: 6px; color: #888; font-size: 16px;
          cursor: pointer; display: flex; align-items: center; justify-content: center;
          transition: all 0.15s;
        }
        .si-close:hover { border-color: #667eea; color: #667eea; }

        /* Drop zone */
        .si-drop {
          border: 1.5px dashed #3a3a4a;
          border-radius: 10px;
          padding: 28px 16px;
          text-align: center;
          cursor: pointer;
          transition: all 0.2s;
          animation: siPulse 3s ease-in-out infinite;
        }
        .si-drop:hover, .si-drop.drag-over {
          border-color: #667eea;
          background: rgba(102, 126, 234, 0.05);
          animation-play-state: paused;
        }
        @keyframes siPulse {
          0%, 100% { border-color: #3a3a4a; }
          50% { border-color: #5a6fd6; }
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
          font-size: 14px; color: #888; margin-bottom: 12px;
        }
        .si-drop-hint {
          font-size: 12px; color: #555; margin-bottom: 16px;
        }
        .si-drop-btns {
          display: flex; gap: 8px; justify-content: center;
        }
        .si-drop-btn {
          padding: 7px 16px;
          border: 1px solid #3a3a4a;
          background: transparent;
          border-radius: 6px;
          color: #888; font-size: 13px; font-weight: 600;
          cursor: pointer; font-family: inherit;
          transition: all 0.15s;
        }
        .si-drop-btn:hover { border-color: #667eea; color: #667eea; }
        .si-drop-btn.primary {
          background: #667eea; border-color: #667eea; color: #fff;
        }
        .si-drop-btn.primary:hover { background: #5a6fd6; }

        /* Error state on drop zone */
        .si-drop.error { border-color: #f87171; animation: none; }
        .si-error-text { color: #f87171; font-size: 13px; margin-top: 8px; }

        /* Preview */
        .si-preview {
          margin-bottom: 12px; text-align: center;
        }
        .si-preview img {
          max-height: 200px; max-width: 100%; border-radius: 8px;
          border: 1px solid #3a3a4a;
        }
        .si-preview-btns {
          display: flex; gap: 8px; justify-content: center; margin-top: 10px;
        }

        /* Parsing overlay */
        .si-parsing {
          position: relative; margin: 12px 0;
          border-radius: 10px; overflow: hidden;
          border: 1.5px dashed #3a3a4a;
        }
        .si-parsing-bg {
          padding: 32px; text-align: center;
        }
        .si-spinner {
          width: 28px; height: 28px;
          border: 2px solid #3a3a4a;
          border-top-color: #667eea;
          border-radius: 50%;
          animation: siSpin 0.7s linear infinite;
          margin: 0 auto 10px;
        }
        @keyframes siSpin { to { transform: rotate(360deg); } }
        .si-parsing-text { font-size: 14px; color: #667eea; }

        /* Results */
        .si-results-header {
          font-size: 14px; font-weight: 600; color: #fff;
          margin-bottom: 12px;
        }
        .si-results-count {
          color: #667eea; margin-left: 4px;
        }
        .si-list { display: flex; flex-direction: column; gap: 8px; margin-bottom: 16px; }
        .si-row {
          display: flex; align-items: center; gap: 8px;
          background: #252836; border-radius: 8px; padding: 10px 12px;
        }
        .si-row input[type="checkbox"] { width: 18px; height: 18px; cursor: pointer; }
        .si-row-info { flex: 1; }
        .si-row-name {
          font-size: 14px; font-weight: 600; color: #e0e0e0;
        }
        .si-row-code {
          font-size: 12px; color: #888; font-family: 'SF Mono', 'Fira Code', monospace;
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
          background: #2a2a2a; color: #888;
          border: 1px solid #3a3a3a;
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
          font-size: 14px; color: #888; margin-bottom: 16px;
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
            <span className="si-title" id="si-title">截图导入</span>
            <button className="si-close" onClick={onClose} aria-label="关闭">✕</button>
          </div>

          {/* Idle / Drop zone */}
          {(phase === 'idle' || phase === 'error') && (
            <div
              ref={dropRef}
              className={`si-drop${errorMsg ? ' error' : ''}`}
              role="button"
              tabIndex={0}
              aria-label="拖拽截图或点击上传"
              onClick={() => fileInputRef.current?.click()}
              onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') fileInputRef.current?.click(); }}
              onDragOver={e => { e.preventDefault(); dropRef.current?.classList.add('drag-over'); }}
              onDragLeave={() => dropRef.current?.classList.remove('drag-over')}
              onDrop={handleDrop}
            >
              <div className="si-drop-icon">📷</div>
              <div className="si-drop-text">拖拽截图或点击上传</div>
              <div className="si-drop-hint">支持 jpg、png、webp，限10MB</div>
              <div className="si-drop-btns">
                <button className="si-drop-btn" onClick={e => { e.stopPropagation(); fileInputRef.current?.click(); }}>
                  选择文件
                </button>
                <button className="si-drop-btn primary" onClick={e => { e.stopPropagation(); fileInputRef.current?.click(); }} capture="environment">
                  拍照
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
                {previewUrl && <img src={previewUrl} alt="截图预览" />}
                <div className="si-preview-btns">
                  <button className="si-drop-btn" onClick={handleRetake}>重新拍照</button>
                  <button className="si-drop-btn primary" onClick={handleUpload}>确认上传</button>
                </div>
              </div>
              <div className="si-parsing">
                <div className="si-parsing-bg">
                  <div className="si-spinner" />
                  <div className="si-parsing-text">识别中...</div>
                </div>
              </div>
            </>
          )}

          {/* Parsing */}
          {phase === 'parsing' && (
            <div className="si-parsing">
              <div className="si-parsing-bg">
                <div className="si-spinner" />
                <div className="si-parsing-text">识别中...</div>
              </div>
            </div>
          )}

          {/* Results */}
          {phase === 'results' && (
            <>
              <div className="si-results-header">
                识别结果（<span className="si-results-count">{holdings.length}</span>只）
              </div>
              <div className="si-list">
                {holdings.map(h => (
                  <div key={h.stock_code} className="si-row">
                    <input
                      type="checkbox"
                      checked={selected.has(h.stock_code)}
                      onChange={() => toggleStock(h.stock_code)}
                      aria-label={`${h.stock_name} ${h.stock_code} 来源${h.source}`}
                    />
                    <div className="si-row-info">
                      <div className="si-row-name">{h.stock_name}</div>
                      <div className="si-row-code">
                        {h.stock_code}
                        <span className={`source-badge ${h.source === '截图' ? 'screenshot' : 'manual'}`}>
                          {h.source}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              <div className="si-actions">
                <button className="btn-primary" onClick={handleConfirm} disabled={selected.size === 0}>
                  确认导入{selected.size > 0 ? ` (${selected.size})` : ''}
                </button>
                <button className="btn-secondary" onClick={onClose}>
                  取消
                </button>
              </div>
            </>
          )}

          {/* Empty */}
          {phase === 'empty' && (
            <div className="si-empty">
              <div className="si-empty-icon">❌</div>
              <div className="si-empty-title">未能识别到股票</div>
              <div className="si-empty-sub">截图不清晰或格式不支持</div>
              <button className="btn-primary" onClick={handleRetake}>重新上传</button>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
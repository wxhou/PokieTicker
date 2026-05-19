import { useState, useRef, useCallback } from 'react';

interface Props {
  children: React.ReactNode;
  onClose: () => void;
  title?: string;
}

export default function BottomSheet({ children, onClose, title }: Props) {
  const [offset, setOffset] = useState(0);
  const startY = useRef(0);
  const sheetRef = useRef<HTMLDivElement>(null);

  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    startY.current = e.touches[0].clientY;
  }, []);

  const handleTouchMove = useCallback((e: React.TouchEvent) => {
    const dy = e.touches[0].clientY - startY.current;
    if (dy > 0) {
      setOffset(dy);
    }
  }, []);

  const handleTouchEnd = useCallback(() => {
    if (offset > window.innerHeight * 0.2) {
      onClose();
    }
    setOffset(0);
  }, [offset, onClose]);

  return (
    <div className="bottom-sheet-backdrop" onClick={onClose}>
      <div
        ref={sheetRef}
        className="bottom-sheet"
        style={{ transform: offset > 0 ? `translateY(${offset}px)` : undefined }}
        onClick={(e) => e.stopPropagation()}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
      >
        <div className="bottom-sheet-handle">
          <div className="bottom-sheet-handle-bar" />
        </div>
        {title && <div className="bottom-sheet-title">{title}</div>}
        <div className="bottom-sheet-content">{children}</div>
      </div>
    </div>
  );
}
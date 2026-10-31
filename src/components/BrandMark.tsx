export function BrandMark({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`brand-lockup ${compact ? 'brand-lockup-compact' : ''}`}>
      <img
        aria-hidden="true"
        alt=""
        src="/smartattend-icon.png"
        className="brand-mark"
        width={40}
        height={40}
      />
      {!compact && (
        <span className="brand-name">
          Smart<span>Attend AI</span>
          <small>ACADEMIC WORKSPACE</small>
          <small className="brand-credit">Developed by Simbu AI/ML from ESEC</small>
        </span>
      )}
    </div>
  );
}

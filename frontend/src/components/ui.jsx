export function Card({ children, className = "" }) {
  return (
    <div className={`bg-surface border border-border rounded-lg p-5 ${className}`}>
      {children}
    </div>
  );
}

export function SectionTitle({ eyebrow, title, action }) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between mb-4">
      <div>
        {eyebrow && (
          <div className="text-amber text-xs stencil uppercase tracking-widest mb-1">{eyebrow}</div>
        )}
        <h2 className="font-display text-xl font-semibold text-text">{title}</h2>
      </div>
      {action}
    </div>
  );
}

export function Button({ children, variant = "primary", className = "", ...props }) {
  const base = "px-4 py-2 rounded-md text-sm font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed";
  const variants = {
    primary: "bg-amber text-bg hover:bg-amber-soft",
    secondary: "bg-surface-2 text-text border border-border hover:border-amber",
    ghost: "text-text-muted hover:text-text",
  };
  return (
    <button className={`${base} ${variants[variant]} ${className}`} {...props}>
      {children}
    </button>
  );
}

export function Input({ label, className = "", ...props }) {
  return (
    <label className="block">
      {label && <span className="block text-xs text-text-muted mb-1">{label}</span>}
      <input
        className={`w-full bg-surface-2 border border-border rounded-md px-3 py-2 text-sm text-text
          focus:outline-none focus:ring-2 focus:ring-amber focus:border-amber ${className}`}
        {...props}
      />
    </label>
  );
}

export function Select({ label, children, className = "", ...props }) {
  return (
    <label className="block">
      {label && <span className="block text-xs text-text-muted mb-1">{label}</span>}
      <select
        className={`w-full bg-surface-2 border border-border rounded-md px-3 py-2 text-sm text-text
          focus:outline-none focus:ring-2 focus:ring-amber focus:border-amber ${className}`}
        {...props}
      >
        {children}
      </select>
    </label>
  );
}

export function Table({ columns, rows, emptyLabel = "Nothing here yet." }) {
  if (!rows || rows.length === 0) {
    return (
      <div className="border border-dashed border-border rounded-md py-10 text-center text-text-muted text-sm">
        {emptyLabel}
      </div>
    );
  }
  return (
    <div className="overflow-x-auto border border-border rounded-md">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-surface-2 text-text-muted text-xs uppercase tracking-wide">
            {columns.map((col) => (
              <th key={col.key} className="text-left px-4 py-2.5 font-medium">
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-t border-border hover:bg-surface-2/50">
              {columns.map((col) => (
                <td key={col.key} className={`px-4 py-2.5 ${col.mono ? "stencil" : ""}`}>
                  {col.render ? col.render(row) : row[col.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Badge({ children, tone = "neutral" }) {
  const tones = {
    neutral: "bg-surface-2 text-text-muted border-border",
    amber: "bg-amber/10 text-amber-soft border-amber/30",
    green: "bg-green/10 text-green border-green/30",
    red: "bg-red/10 text-red border-red/30",
  };
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs border stencil ${tones[tone]}`}>
      {children}
    </span>
  );
}

export function RowActions({ onEdit, onDelete, deleteLabel = "Delete", deleteConfirm = "Are you sure?", deleteDisabledReason }) {
  return (
    <div className="flex items-center gap-3 text-xs">
      {onEdit && (
        <button type="button" onClick={onEdit} className="text-amber-soft hover:underline">
          Edit
        </button>
      )}
      {onDelete && (
        deleteDisabledReason ? (
          <span className="text-text-muted cursor-not-allowed" title={deleteDisabledReason}>{deleteLabel}</span>
        ) : (
          <button
            type="button"
            onClick={() => { if (window.confirm(deleteConfirm)) onDelete(); }}
            className="text-red hover:underline"
          >
            {deleteLabel}
          </button>
        )
      )}
    </div>
  );
}

export function formatPKR(amount) {
  return new Intl.NumberFormat("en-PK", { maximumFractionDigits: 0 }).format(amount || 0);
}

export function Modal({ title, onClose, children, wide = false }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div
        className={`bg-surface border border-border rounded-lg p-6 w-full ${wide ? "max-w-2xl" : "max-w-md"} max-h-[90vh] overflow-y-auto`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-display text-lg font-semibold">{title}</h3>
          <button type="button" onClick={onClose} className="text-text-muted hover:text-text text-lg leading-none">✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}

import { useState, useRef, useEffect } from 'react'

export default function PriceSummaryCard({ label, value, format, positive, subLabel, formulaBreakdown }) {
  const formatted = formatValue(value, format, positive)
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-5 relative">
      <div className="flex items-center gap-2 mb-1">
        <p className="text-xs font-medium uppercase tracking-wider text-slate-500">{label}</p>
        {formulaBreakdown && (
          <button
            onClick={() => setOpen(!open)}
            className="flex h-4 w-4 items-center justify-center rounded-full border border-slate-600 text-[10px] text-slate-500 hover:border-slate-400 hover:text-slate-300 transition-colors"
            title="How is this calculated?"
          >
            ?
          </button>
        )}
      </div>
      <p className={`text-2xl font-bold ${formatted.color}`}>
        {formatted.text}
      </p>
      {subLabel && (
        <p className="mt-1 text-xs text-slate-500">{subLabel}</p>
      )}

      {open && formulaBreakdown && (
        <div
          ref={ref}
          className="absolute left-0 top-full z-50 mt-2 w-80 rounded-xl border border-slate-700 bg-slate-900 p-4 shadow-2xl"
        >
          <h4 className="text-sm font-semibold text-white mb-3">How this is calculated</h4>
          <p className="text-xs text-slate-300 mb-1">{formulaBreakdown.methodLabel}</p>
          <div className="rounded-lg bg-slate-800 p-3 mb-2 font-mono text-xs text-slate-300">
            {formulaBreakdown.formulaLines.map((line, i) => (
              <div key={i}>{line}</div>
            ))}
          </div>
          {formulaBreakdown.note && (
            <p className="text-xs text-slate-500">{formulaBreakdown.note}</p>
          )}
        </div>
      )}
    </div>
  )
}

function formatValue(value, format, positive) {
  if (value == null) return { text: '—', color: 'text-slate-500' }

  if (format === 'currency') {
    return { text: `$${Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })}`, color: 'text-white' }
  }
  if (format === 'percent') {
    const n = Number(value)
    const sign = n >= 0 ? '+' : ''
    const color = n > 0 ? 'text-emerald-400' : n < 0 ? 'text-red-400' : 'text-slate-400'
    return { text: `${sign}${n.toFixed(1)}%`, color }
  }
  return { text: String(value), color: 'text-white' }
}

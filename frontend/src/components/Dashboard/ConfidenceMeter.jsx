import { useState, useRef, useEffect } from 'react'

export default function ConfidenceMeter({ score, label, breakdown }) {
  const pct = Math.round((score || 0) * 100)
  const barColor =
    pct >= 80 ? 'bg-emerald-500' :
    pct >= 50 ? 'bg-amber-500' :
    'bg-red-500'
  const textColor =
    pct >= 80 ? 'text-emerald-400' :
    pct >= 50 ? 'text-amber-400' :
    'text-red-400'

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
      <div className="flex items-center gap-2 mb-2">
        <p className="text-xs font-medium uppercase tracking-wider text-slate-500">Confidence</p>
        <button
          onClick={() => setOpen(!open)}
          className="flex h-4 w-4 items-center justify-center rounded-full border border-slate-600 text-[10px] text-slate-500 hover:border-slate-400 hover:text-slate-300 transition-colors"
          title="How is this calculated?"
        >
          ?
        </button>
      </div>

      <div className="flex items-end gap-3">
        <span className={`text-3xl font-bold ${textColor}`}>{pct}%</span>
        {label && <span className={`rounded px-2 py-0.5 text-xs font-medium ${textColor} bg-slate-800`}>{label}</span>}
      </div>

      <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-800">
        <div className={`h-full rounded-full transition-all duration-700 ${barColor}`} style={{ width: `${pct}%` }} />
      </div>

      {open && breakdown && (
        <div
          ref={ref}
          className="absolute right-0 top-full z-50 mt-2 w-80 rounded-xl border border-slate-700 bg-slate-850 bg-slate-900 p-4 shadow-2xl"
        >
          <h4 className="text-sm font-semibold text-white mb-3">How confidence is calculated</h4>

          {breakdown.guidance && Object.keys(breakdown.guidance).length > 0 && (
            <Section title="Guidance Confidence" items={[
              {
                label: 'Source quality',
                detail: `Avg weight: ${(breakdown.guidance.avg_source_weight * 100).toFixed(0)}% across ${breakdown.guidance.unique_sources} source(s)`,
                value: breakdown.guidance.source_quality,
                weight: 0.4,
              },
              {
                label: 'Source diversity',
                detail: `${breakdown.guidance.unique_sources} distinct source(s)`,
                value: breakdown.guidance.source_diversity,
                weight: 0.2,
              },
              {
                label: 'Consensus tightness',
                detail: breakdown.guidance.cv != null
                  ? `${breakdown.guidance.eps_items_count} EPS items, spread ${(breakdown.guidance.cv * 100).toFixed(1)}%`
                  : `${breakdown.guidance.eps_items_count} EPS item(s)`,
                value: breakdown.guidance.consensus_tightness,
                weight: 0.2,
              },
              {
                label: 'Recency',
                detail: breakdown.guidance.days_since_guidance != null
                  ? `${breakdown.guidance.days_since_guidance} day(s) since guidance`
                  : 'Not available',
                value: breakdown.guidance.recency,
                weight: 0.1,
              },
              ...(breakdown.guidance.hallucination_penalty > 0 ? [{
                label: 'Hallucination penalty',
                detail: `Penalty applied`,
                value: -breakdown.guidance.hallucination_penalty,
                weight: null,
              }] : []),
              {
                label: 'Guidance type',
                detail: `Modifier: ${(breakdown.guidance.guidance_type_modifier * 100).toFixed(0)}%`,
                value: null,
                weight: null,
                note: `Guidance confidence = sum above × ${(breakdown.guidance.guidance_type_modifier * 100).toFixed(0)}% modifier`,
              },
            ]} />
          )}

          {breakdown.valuation && Object.keys(breakdown.valuation).length > 0 && (
            <Section title="Valuation Confidence" items={[
              ...(breakdown.valuation.capped
                ? [{
                    label: breakdown.valuation.capped === 'negative_eps' ? 'Negative EPS cap' : 'No guidance cap',
                    detail: 'Valuation confidence capped',
                    value: null,
                    weight: null,
                  }]
                : [
                    {
                      label: 'Guidance contribution',
                      detail: `${(breakdown.guidance?.guidance_type_modifier ? (breakdown.valuation.guidance_contrib / (score || 1) * 100) : 70).toFixed(0)}% of final`,
                      value: breakdown.valuation.guidance_contrib,
                      weight: 0.7,
                    },
                    {
                      label: 'PE history',
                      detail: `${breakdown.valuation.pe_observations || 0} observations (${((breakdown.valuation.pe_bonus_factor || 0) * 100).toFixed(0)}% of max bonus)`,
                      value: breakdown.valuation.pe_history_contrib,
                      weight: 0.3,
                    },
                  ]
              ),
            ]} />
          )}

          <div className="mt-3 pt-3 border-t border-slate-700 text-xs text-slate-400">
            <span className="text-slate-500">Thresholds: </span>
            <span className="text-emerald-400">HIGH</span> ≥ 80% ·{' '}
            <span className="text-amber-400">MEDIUM</span> ≥ 50% ·{' '}
            <span className="text-red-400">LOW</span> &lt; 50%
          </div>
        </div>
      )}
    </div>
  )
}

function Section({ title, items }) {
  return (
    <div className="mb-3">
      <h5 className="text-xs font-medium text-slate-400 mb-2">{title}</h5>
      {items.map((item, i) => (
        <div key={i} className="flex items-center justify-between py-1 text-xs">
          <div>
            <span className="text-slate-300">{item.label}</span>
            {item.weight != null && (
              <span className="text-slate-600 ml-1">({(item.weight * 100).toFixed(0)}%)</span>
            )}
            {item.detail && (
              <div className="text-slate-500">{item.detail}</div>
            )}
            {item.note && (
              <div className="text-slate-500 italic mt-0.5">{item.note}</div>
            )}
          </div>
          {item.value != null && (
            <span className={`ml-2 tabular-nums ${item.value >= 0 ? 'text-slate-300' : 'text-red-400'}`}>
              {item.value >= 0 ? '+' : ''}{item.value.toFixed(3)}
            </span>
          )}
        </div>
      ))}
    </div>
  )
}

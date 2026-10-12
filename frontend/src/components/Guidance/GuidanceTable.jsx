export default function GuidanceTable({ guidance }) {
  const items = []
  if (guidance.eps_guidance) items.push({ label: 'EPS', ...guidance.eps_guidance })
  if (guidance.revenue_guidance) items.push({ label: 'Revenue', ...guidance.revenue_guidance })
  if (guidance.gross_margin_guidance) items.push({ label: 'Gross Margin', ...guidance.gross_margin_guidance })

  if (items.length === 0) return null

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-medium text-slate-300">Extracted Guidance</h3>
        <span className="rounded bg-indigo-950/50 px-2 py-0.5 text-xs text-indigo-300">
          {guidance.items_found} item{guidance.items_found !== 1 ? 's' : ''} found
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-800 text-left text-xs uppercase text-slate-500">
              <th className="pb-2 pr-4">Metric</th>
              <th className="pb-2 pr-4">Guidance</th>
              <th className="pb-2 pr-4">Period</th>
              <th className="pb-2 pr-4">Type</th>
              <th className="pb-2 pr-4">Source</th>
              <th className="pb-2">Confidence</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item, i) => (
              <tr key={i} className="border-b border-slate-800/50">
                <td className="py-3 pr-4 font-medium text-white">{item.label}</td>
                <td className="py-3 pr-4 text-slate-300">
                  {item.value_midpoint != null
                    ? fmtGuidance(item.value_midpoint, item.unit)
                    : item.value_low != null && item.value_high != null
                      ? `${fmtGuidance(item.value_low, item.unit)} – ${fmtGuidance(item.value_high, item.unit)}`
                      : '—'}
                </td>
                <td className="py-3 pr-4 text-slate-400">{item.period_label || '—'}</td>
                <td className="py-3 pr-4">
                  <GuidanceTypeBadge type={item.guidance_type} />
                </td>
                <td className="py-3 pr-4">
                  <span className={`rounded px-2 py-0.5 text-xs ${item.is_official_guidance ? 'bg-emerald-950/50 text-emerald-400' : 'bg-amber-950/50 text-amber-400'}`}>
                    {item.is_official_guidance ? 'Official' : 'Analyst'}
                  </span>
                </td>
                <td className="py-3">
                  <ConfidenceBadge level={item.confidence} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {guidance.conflict_detected && (
        <p className="mt-3 text-xs text-amber-400">Conflicting guidance detected across sources</p>
      )}
    </div>
  )
}

function GuidanceTypeBadge({ type }) {
  const colors = {
    raised: 'bg-emerald-950/50 text-emerald-400',
    lowered: 'bg-red-950/50 text-red-400',
    reiterated: 'bg-blue-950/50 text-blue-400',
    initial: 'bg-slate-800 text-slate-300',
    withdrawn: 'bg-red-950/50 text-red-400',
  }
  const c = colors[type] || colors.initial
  return <span className={`rounded px-2 py-0.5 text-xs ${c}`}>{type || 'initial'}</span>
}

function ConfidenceBadge({ level }) {
  const colors = {
    high: 'bg-emerald-950/50 text-emerald-400',
    medium: 'bg-amber-950/50 text-amber-400',
    low: 'bg-red-950/50 text-red-400',
  }
  const c = colors[level] || colors.medium
  return <span className={`rounded px-2 py-0.5 text-xs ${c}`}>{level || 'medium'}</span>
}

function fmtGuidance(v, unit) {
  const n = Number(v)
  if (unit === 'USD_billions') return `$${n.toFixed(2)}B`
  if (unit === 'USD_millions') return `$${n.toFixed(0)}M`
  if (unit === 'percent') return `${n.toFixed(1)}%`
  return `$${n.toFixed(2)}`
}

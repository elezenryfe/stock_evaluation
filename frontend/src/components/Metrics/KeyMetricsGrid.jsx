const METRICS = [
  { key: 'current_eps_ttm', label: 'EPS (TTM)', format: 'num' },
  { key: 'current_pe_ttm', label: 'P/E (TTM)', format: 'num' },
  { key: 'current_revenue_ttm', label: 'Revenue (TTM)', format: 'billions' },
  { key: 'market_cap', label: 'Market Cap', format: 'billions' },
  { key: 'median_pe', label: 'Median PE (5yr)', format: 'num' },
  { key: 'pe_observations', label: 'PE Data Points', format: 'int' },
]

export default function KeyMetricsGrid({ result, guidance }) {
  const guidanceEps = guidance?.eps_guidance?.value_midpoint
  const isNegativeEps = result.negative_eps_flag

  return (
    <div className="grid flex-1 grid-cols-3 gap-3">
      {guidanceEps && (
        <MetricCell label="Guidance EPS" value={guidanceEps} format="num" highlight />
      )}
      <MetricCell label="EPS (TTM)" value={result.current_eps_ttm} format="num" negative={isNegativeEps} />
      <MetricCell label="P/E (TTM)" value={result.current_pe_ttm} format="num" />
      <MetricCell label="Revenue (TTM)" value={result.current_revenue_ttm} format="billions" />
      <MetricCell label="Market Cap" value={result.market_cap} format="billions" />
      <MetricCell label="Median PE (5yr)" value={result.median_pe} format="num" />
      {result.peg_health?.peg_ratio && (
        <MetricCell label="PEG Ratio" value={result.peg_health.peg_ratio} format="num" />
      )}
      {result.pe_observations && (
        <MetricCell label="PE Obs." value={result.pe_observations} format="int" />
      )}
    </div>
  )
}

function MetricCell({ label, value, format, highlight, negative }) {
  const formatted = fmt(value, format)
  return (
    <div className={`rounded-lg border p-3 ${highlight ? 'border-indigo-800 bg-indigo-950/30' : 'border-slate-800 bg-slate-900'}`}>
      <p className="text-[10px] font-medium uppercase tracking-wider text-slate-500">{label}</p>
      <p className={`text-sm font-bold ${negative ? 'text-red-400' : highlight ? 'text-indigo-300' : 'text-slate-200'}`}>
        {formatted}
      </p>
    </div>
  )
}

function fmt(v, f) {
  if (v == null) return '—'
  const n = Number(v)
  if (f === 'billions' && n > 1e9) return `$${(n / 1e9).toFixed(1)}B`
  if (f === 'billions' && n > 1e6) return `$${(n / 1e6).toFixed(0)}M`
  if (f === 'num') return n >= 10 ? n.toLocaleString(undefined, { maximumFractionDigits: 1 }) : n.toFixed(2)
  if (f === 'int') return String(Math.round(n))
  return String(n)
}

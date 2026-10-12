import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'

export default function PEHistoryChart({ result }) {
  const { median_pe, pe_p25, pe_p75, pe_years_used, pe_observations } = result
  if (!median_pe) return null

  const data = [
    { name: 'P25', value: pe_p25 || median_pe * 0.6, fill: '#ef4444' },
    { name: 'Median', value: median_pe, fill: '#6366f1' },
    { name: 'P75', value: pe_p75 || median_pe * 1.4, fill: '#22c55e' },
  ]

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
      <h3 className="mb-1 text-sm font-medium text-slate-300">
        Historical PE Ratio ({pe_years_used || 5}-Year)
      </h3>
      <p className="mb-4 text-xs text-slate-500">{pe_observations || 0} quarterly observations</p>
      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={data} margin={{ top: 10, right: 10, left: 10, bottom: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis dataKey="name" stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 12 }} />
          <YAxis stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 12 }} tickFormatter={(v) => `${v}x`} />
          <Tooltip
            contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }}
            labelStyle={{ color: '#e2e8f0' }}
            formatter={(v) => [`${Number(v).toFixed(1)}x`, 'PE Ratio']}
          />
          <ReferenceLine y={median_pe} stroke="#6366f1" strokeDasharray="3 3" />
          <Bar dataKey="value" radius={[4, 4, 0, 0]}>
            {data.map((d, i) => <Cell key={i} fill={d.fill} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function Cell({ fill, ...props }) {
  return <rect fill={fill} {...props} />
}

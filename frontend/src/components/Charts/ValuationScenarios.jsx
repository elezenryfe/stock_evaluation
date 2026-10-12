import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer, Cell } from 'recharts'

export default function ValuationScenarios({ result }) {
  const { current_price, bear_price, estimated_price, bull_price } = result
  if (!estimated_price) return null

  const data = [
    { name: 'Bear', price: bear_price || estimated_price * 0.7, fill: '#ef4444' },
    { name: 'Base', price: estimated_price, fill: '#6366f1' },
    { name: 'Bull', price: bull_price || estimated_price * 1.3, fill: '#22c55e' },
  ]

  const formatPrice = (v) => `$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
      <h3 className="mb-4 text-sm font-medium text-slate-300">Valuation Scenarios</h3>
      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={data} margin={{ top: 10, right: 10, left: 10, bottom: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis dataKey="name" stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 12 }} />
          <YAxis stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 12 }} tickFormatter={formatPrice} />
          <Tooltip
            contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }}
            labelStyle={{ color: '#e2e8f0' }}
            formatter={(v) => [formatPrice(v), '']}
          />
          {current_price && (
            <ReferenceLine y={current_price} stroke="#f59e0b" strokeDasharray="5 5" label={{ value: 'Current', fill: '#f59e0b', fontSize: 11 }} />
          )}
          <Bar dataKey="price" radius={[4, 4, 0, 0]}>
            {data.map((d, i) => <Cell key={i} fill={d.fill} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

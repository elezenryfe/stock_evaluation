import SourceCard from './SourceCard'

export default function SourceList({ sources }) {
  const grouped = sources.reduce((acc, s) => {
    const type = s.source_type || 'other'
    if (!acc[type]) acc[type] = []
    acc[type].push(s)
    return acc
  }, {})

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
      <h3 className="mb-4 text-sm font-medium text-slate-300">
        Sources ({sources.length} document{sources.length !== 1 ? 's' : ''})
      </h3>
      {Object.entries(grouped).map(([type, docs]) => (
        <div key={type} className="mb-4">
          <p className="mb-2 text-xs font-medium uppercase tracking-wider text-slate-500">
            {type.replace('SEC_', 'SEC ').replace('_', ' ')} ({docs.length})
          </p>
          <div className="grid gap-2 sm:grid-cols-2">
            {docs.map((doc, i) => (
              <SourceCard key={i} source={doc} />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

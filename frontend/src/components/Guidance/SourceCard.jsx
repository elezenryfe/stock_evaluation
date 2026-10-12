export default function SourceCard({ source }) {
  const typeLabel = source.source_type?.replace('SEC_', 'SEC ').replace('_', ' ') || 'Document'

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-4 transition hover:border-slate-700">
      <div className="mb-2 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-slate-200">{source.document_title}</p>
          {source.document_date && (
            <p className="text-xs text-slate-500">{source.document_date}</p>
          )}
        </div>
        <span className="shrink-0 rounded bg-slate-800 px-2 py-0.5 text-[10px] font-medium uppercase text-slate-400">
          {typeLabel}
        </span>
      </div>
      <div className="flex items-center justify-between">
        <span className="text-xs text-slate-500">{source.word_count?.toLocaleString()} words</span>
        <a
          href={source.url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-indigo-400 hover:text-indigo-300"
        >
          View source ↗
        </a>
      </div>
    </div>
  )
}

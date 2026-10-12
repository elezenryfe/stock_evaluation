import useAppStore from '../../store/useAppStore'

export default function RecentSearches({ onSelect }) {
  const recent = useAppStore((s) => s.recentSearches)
  if (recent.length === 0) return null

  return (
    <div className="mt-8">
      <h3 className="mb-3 text-sm font-medium text-slate-500">Recent</h3>
      <div className="flex flex-wrap gap-2">
        {recent.map((t) => (
          <button
            key={t}
            onClick={() => onSelect(t)}
            className="rounded-full border border-slate-700 bg-slate-800 px-4 py-1.5 text-sm text-slate-300 transition hover:border-indigo-500 hover:text-white"
          >
            {t}
          </button>
        ))}
      </div>
    </div>
  )
}

export default function LoadingSpinner({ stage, message, pct }) {
  return (
    <div className="flex flex-col items-center justify-center py-20">
      <div className="mb-6 h-3 w-64 overflow-hidden rounded-full bg-slate-800">
        <div
          className="h-full rounded-full bg-indigo-500 transition-all duration-500"
          style={{ width: `${Math.max(pct || 2, 2)}%` }}
        />
      </div>
      <p className="text-sm font-medium text-slate-300 capitalize">{message || stage || 'Loading...'}</p>
      <p className="mt-1 text-xs text-slate-500">{pct || 0}%</p>
    </div>
  )
}

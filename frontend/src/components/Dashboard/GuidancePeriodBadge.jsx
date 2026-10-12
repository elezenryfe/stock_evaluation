export default function GuidancePeriodBadge({ period }) {
  if (!period) return null
  return (
    <span className="rounded-full border border-indigo-800 bg-indigo-950/50 px-4 py-1.5 text-sm font-medium text-indigo-300">
      {period}
    </span>
  )
}

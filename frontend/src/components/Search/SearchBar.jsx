import { useState, useEffect, useRef } from 'react'
import api from '../../api/client'

const TICKER_RE = /^[A-Z0-9.\-]{1,20}$/

export default function SearchBar({ onSelect, compact }) {
  const [query, setQuery] = useState('')
  const [suggestions, setSuggestions] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const timerRef = useRef(null)

  useEffect(() => {
    if (!query || query.length < 1) {
      setSuggestions([])
      setError('')
      return
    }
    const upper = query.toUpperCase()
    if (!TICKER_RE.test(upper)) {
      setSuggestions([])
      setError(upper.length > 1 ? 'Letters, numbers, dots, dashes only' : '')
      return
    }
    setError('')
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(async () => {
      setLoading(true)
      try {
        const res = await api.get(`/stocks/${upper}/validate`)
        setSuggestions([res.data])
      } catch {
        setSuggestions([])
      }
      setLoading(false)
    }, 300)
    return () => { if (timerRef.current) clearTimeout(timerRef.current) }
  }, [query])

  const handleSubmit = (e) => {
    e.preventDefault()
    const upper = query.trim().toUpperCase()
    if (TICKER_RE.test(upper)) {
      setQuery('')
      onSelect(upper)
    }
  }

  const handleSuggestionClick = (ticker) => {
    setQuery('')
    setSuggestions([])
    onSelect(ticker)
  }

  return (
    <div className={compact ? '' : 'w-full'}>
      <form onSubmit={handleSubmit} className="relative">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Enter ticker (e.g. NVDA, RELIANCE.NS, SHEL.L)"
          className={`w-full rounded-lg border bg-slate-800 px-4 text-white placeholder-slate-500 outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 ${compact ? 'border-slate-700 py-2 text-sm' : 'border-slate-600 py-3 text-lg'}`}
        />
        <button type="submit" className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white">
          {loading ? '...' : '&#8594;'}
        </button>
      </form>
      {error && <p className="mt-1 text-xs text-red-400">{error}</p>}
      {suggestions.length > 0 && (
        <div className="mt-1 rounded-lg border border-slate-700 bg-slate-800 py-1">
          {suggestions.map((s) => (
            <button
              key={s.ticker}
              onClick={() => handleSuggestionClick(s.ticker)}
              className="w-full px-4 py-2 text-left text-sm text-white hover:bg-slate-700"
            >
              <span className="font-medium">{s.ticker}</span>
              <span className="ml-2 text-slate-400">{s.company_name}</span>
              {s.exchange && <span className="ml-1 text-xs text-slate-500">({s.exchange})</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

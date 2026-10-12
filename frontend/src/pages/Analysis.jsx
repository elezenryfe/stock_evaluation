import { useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useAnalysis } from '../hooks/useAnalysis'
import useAppStore from '../store/useAppStore'
import SearchBar from '../components/Search/SearchBar'
import DashboardLayout from '../components/Dashboard/DashboardLayout'
import LoadingSpinner from '../components/Common/LoadingSpinner'

export default function Analysis() {
  const { ticker } = useParams()
  const navigate = useNavigate()
  const addRecent = useAppStore((s) => s.addRecent)
  const { startAnalysis, reset, status, result, progress } = useAnalysis()

  useEffect(() => {
    if (ticker) {
      addRecent(ticker.toUpperCase())
      reset()
      startAnalysis(ticker.toUpperCase())
    }
  }, [ticker])

  const handleSearch = (t) => {
    navigate(`/analysis/${t}`)
  }

  return (
    <div className="min-h-screen bg-slate-950">
      <nav className="border-b border-slate-800 bg-slate-900 px-4 py-3">
        <div className="mx-auto flex max-w-6xl items-center gap-4">
          <button onClick={() => navigate('/')} className="text-lg font-bold text-white">
            StockGuide
          </button>
          <div className="flex-1 max-w-md">
            <SearchBar onSelect={handleSearch} compact />
          </div>
        </div>
      </nav>

      <div className="mx-auto max-w-6xl px-4 py-8">
        {status === 'loading' && (
          <LoadingSpinner stage={progress.stage} message={progress.message} pct={progress.pct} />
        )}
        {status === 'error' && (
          <div className="rounded-lg border border-red-800 bg-red-950/30 p-6 text-center">
            <p className="text-lg text-red-400">{progress.message || 'Analysis failed'}</p>
            <button onClick={() => startAnalysis(ticker)} className="mt-3 text-sm text-slate-400 underline">
              Retry
            </button>
          </div>
        )}
        {status === 'complete' && result && (
          <DashboardLayout data={result} />
        )}
      </div>
    </div>
  )
}

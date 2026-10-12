import { useNavigate } from 'react-router-dom'
import SearchBar from '../components/Search/SearchBar'
import RecentSearches from '../components/Search/RecentSearches'
import useAppStore from '../store/useAppStore'

export default function Home() {
  const navigate = useNavigate()
  const addRecent = useAppStore((s) => s.addRecent)

  const handleSearch = (ticker) => {
    addRecent(ticker)
    navigate(`/analysis/${ticker}`)
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-24">
      <div className="mb-12 text-center">
        <h1 className="mb-3 text-4xl font-bold tracking-tight text-white">
          Stock Guidance Analyzer
        </h1>
        <p className="text-lg text-slate-400">
          Enter a ticker to extract official company guidance and calculate forward valuation
        </p>
      </div>
      <SearchBar onSelect={handleSearch} />
      <RecentSearches onSelect={handleSearch} />
    </div>
  )
}

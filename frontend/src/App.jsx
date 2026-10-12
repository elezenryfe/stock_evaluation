import { Routes, Route } from 'react-router-dom'
import Home from './pages/Home'
import Analysis from './pages/Analysis'

export default function App() {
  return (
    <div className="min-h-screen bg-slate-950">
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/analysis/:ticker" element={<Analysis />} />
      </Routes>
    </div>
  )
}

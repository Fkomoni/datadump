import { useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import FileUpload from './components/FileUpload'
import ProviderAnalytics from './pages/ProviderAnalytics'
import TariffIntelligence from './pages/TariffIntelligence'
import FWAInsights from './pages/FWAInsights'
import TariffMapper from './pages/TariffMapper'
import PlanAccess from './pages/PlanAccess'

export default function App() {
  const [session, setSession] = useState(null)

  if (!session) {
    return <FileUpload onUpload={setSession} />
  }

  return (
    <BrowserRouter>
      <div className="flex h-screen overflow-hidden">
        <Sidebar session={session} onReset={() => setSession(null)} />
        <main className="flex-1 overflow-y-auto bg-lh-cream p-8">
          <Routes>
            <Route path="/" element={<Navigate to="/provider-analytics" replace />} />
            <Route path="/provider-analytics" element={<ProviderAnalytics session={session} />} />
            <Route path="/tariff-intelligence" element={<TariffIntelligence session={session} />} />
            <Route path="/fwa-insights" element={<FWAInsights session={session} />} />
            <Route path="/tariff-mapper" element={<TariffMapper session={session} />} />
            <Route path="/plan-access" element={<PlanAccess session={session} />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

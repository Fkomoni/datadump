import { useState, useEffect, useCallback } from 'react'
import StatCard from '../components/StatCard'
import DataTable from '../components/DataTable'

const API = '/api'
const fmt = n => n != null ? Number(n).toLocaleString() : '0'

const SUB_TABS = [
  { key: 'overview', label: 'Overview' },
  { key: 'groups', label: 'Groups' },
  { key: 'schemes', label: 'Schemes' },
  { key: 'top-lines', label: 'Top 30 Lines' },
  { key: 'chronic', label: 'Chronic Meds' },
  { key: 'simulation', label: 'Simulation' },
  { key: 'high-cost', label: 'High Cost Cases' },
  { key: 'bundling', label: 'Bundling Flags' },
  { key: 'enrollees', label: 'Enrollee Analysis' },
]

export default function ProviderAnalytics({ session }) {
  const [tab, setTab] = useState('overview')
  const [provider, setProvider] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [discountPct, setDiscountPct] = useState(20)

  const fetchData = useCallback(async (t) => {
    setLoading(true)
    setData(null)
    const params = new URLSearchParams({ session_id: session.session_id })
    if (provider) params.append('provider_name', provider)
    if (dateFrom) params.append('date_from', dateFrom)
    if (dateTo) params.append('date_to', dateTo)

    let url = ''
    switch (t || tab) {
      case 'overview': url = `${API}/provider/overview`; break
      case 'groups': url = `${API}/provider/groups`; break
      case 'schemes': url = `${API}/provider/schemes`; break
      case 'top-lines': url = `${API}/provider/top-lines`; break
      case 'chronic': url = `${API}/provider/chronic`; break
      case 'simulation': params.append('discount_pct', discountPct); url = `${API}/provider/simulate`; break
      case 'high-cost': url = `${API}/provider/high-cost-cases`; break
      case 'bundling': url = `${API}/provider/bundling-flags`; break
      case 'enrollees': url = `${API}/client/enrollees`; break
      default: url = `${API}/provider/overview`
    }

    try {
      const res = await fetch(`${url}?${params}`)
      const json = await res.json()
      setData(json)
    } catch { setData(null) }
    setLoading(false)
  }, [session.session_id, provider, dateFrom, dateTo, tab, discountPct])

  useEffect(() => { fetchData() }, [tab])

  function handleApply(e) { e.preventDefault(); fetchData() }

  function handleExport() {
    const params = new URLSearchParams({ session_id: session.session_id })
    if (provider) params.append('provider_name', provider)
    if (dateFrom) params.append('date_from', dateFrom)
    if (dateTo) params.append('date_to', dateTo)
    fetch(`${API}/provider/export-all?${params}`, { method: 'POST' })
      .then(r => r.blob())
      .then(b => {
        const url = URL.createObjectURL(b)
        const a = document.createElement('a'); a.href = url
        a.download = `${(provider || 'All').replace(/ /g, '_')}_Analytics.xlsx`
        a.click(); URL.revokeObjectURL(url)
      })
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-extrabold text-lh-dark">Provider Analytics</h1>
          <p className="text-sm text-gray-400">Performance, cost, and utilisation deep dive</p>
        </div>
        <button onClick={handleExport} className="px-4 py-2 bg-lh-dark text-white text-xs font-bold rounded-lg hover:bg-lh-navy">⬇ Export All</button>
      </div>

      {/* Filter Bar */}
      <form onSubmit={handleApply} className="bg-white rounded-xl p-4 mb-4 shadow-sm flex items-end gap-3 flex-wrap">
        <div className="flex-1 min-w-[200px]">
          <label className="text-[10px] font-bold uppercase text-gray-400 block mb-1">Provider</label>
          <select value={provider} onChange={e => setProvider(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm bg-gray-50 focus:border-lh-red focus:outline-none">
            <option value="">All Providers</option>
            {(session.unique_providers || []).map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
        <div>
          <label className="text-[10px] font-bold uppercase text-gray-400 block mb-1">Date From</label>
          <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
                 className="px-3 py-2 border border-gray-200 rounded-lg text-sm bg-gray-50 focus:border-lh-red focus:outline-none" />
        </div>
        <div>
          <label className="text-[10px] font-bold uppercase text-gray-400 block mb-1">Date To</label>
          <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
                 className="px-3 py-2 border border-gray-200 rounded-lg text-sm bg-gray-50 focus:border-lh-red focus:outline-none" />
        </div>
        <button type="submit" className="px-5 py-2 bg-lh-red text-white text-xs font-bold rounded-lg hover:bg-red-700">Apply</button>
      </form>

      {/* Sub tabs */}
      <div className="flex gap-1 mb-6 overflow-x-auto pb-1">
        {SUB_TABS.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
                  className={`px-4 py-2 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors ${
                    tab === t.key ? 'bg-lh-dark text-white' : 'bg-white text-gray-500 hover:bg-gray-100'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Loading */}
      {loading && <div className="text-center py-16 text-gray-400"><div className="text-3xl animate-pulse mb-2">⏳</div>Loading...</div>}

      {/* Content */}
      {!loading && data && (
        <>
          {tab === 'overview' && <OverviewTab data={data} />}
          {tab === 'groups' && <GroupsTab data={data} />}
          {tab === 'schemes' && <SchemesTab data={data} />}
          {tab === 'top-lines' && <TopLinesTab data={data} />}
          {tab === 'chronic' && <ChronicTab data={data} />}
          {tab === 'simulation' && <SimulationTab data={data} discount={discountPct} setDiscount={setDiscountPct} onRefresh={() => fetchData('simulation')} />}
          {tab === 'high-cost' && <HighCostTab data={data} onRegenerate={() => fetchData('high-cost')} />}
          {tab === 'bundling' && <BundlingTab data={data} onRegenerate={() => fetchData('bundling')} />}
          {tab === 'enrollees' && <EnrolleeTab data={data} />}
        </>
      )}

      {!loading && !data && <div className="text-center py-16 text-gray-400">No data available. Select a provider and click Apply.</div>}
    </div>
  )
}

function OverviewTab({ data }) {
  const s = data.summary || {}
  return (
    <>
      <div className="grid grid-cols-4 gap-4 mb-6">
        <StatCard label="Total Spend" value={fmt(s.total_spend)} />
        <StatCard label="Unique Members" value={fmt(data.cumulative_unique_members)} />
        <StatCard label="Unique Visits" value={fmt(s.total_claims)} />
        <StatCard label="Avg Per Visit" value={fmt(s.avg_per_visit)} />
      </div>
      <DataTable exportName="overview" columns={[
        { key: 'month', label: 'Month' },
        { key: 'amount_paid', label: 'Amount Paid', align: 'right', format: v => fmt(v) },
        { key: 'unique_members', label: 'Unique Members', align: 'right', format: v => fmt(v) },
        { key: 'unique_visits', label: 'Unique Visits', align: 'right', format: v => fmt(v) },
      ]} data={data.monthly || []} />
    </>
  )
}

function GroupsTab({ data }) {
  return <DataTable exportName="groups" columns={[
    { key: 'group', label: 'Group' },
    { key: 'amount_paid', label: 'Amount Paid', align: 'right', format: v => fmt(v) },
    { key: 'unique_members', label: 'Members', align: 'right', format: v => fmt(v) },
    { key: 'unique_visits', label: 'Visits', align: 'right', format: v => fmt(v) },
  ]} data={data.data || []} />
}

function SchemesTab({ data }) {
  return <DataTable exportName="schemes" columns={[
    { key: 'scheme', label: 'Scheme' },
    { key: 'amount_paid', label: 'Amount Paid', align: 'right', format: v => fmt(v) },
    { key: 'unique_members', label: 'Members', align: 'right', format: v => fmt(v) },
    { key: 'unique_visits', label: 'Visits', align: 'right', format: v => fmt(v) },
  ]} data={data.data || []} />
}

function TopLinesTab({ data }) {
  return <DataTable exportName="top30_lines" columns={[
    { key: 'rank', label: '#', align: 'right' },
    { key: 'service', label: 'Service (Tariff Descr)' },
    { key: 'amount_paid', label: 'Amount Paid', align: 'right', format: v => fmt(v) },
    { key: 'unique_members', label: 'Members', align: 'right', format: v => fmt(v) },
    { key: 'times_utilized', label: 'Times Utilized', align: 'right', format: v => fmt(v) },
    { key: 'avg_paid_per_line', label: 'Avg Per Line', align: 'right', format: v => fmt(v) },
  ]} data={data.data || []} />
}

function ChronicTab({ data }) {
  return (
    <>
      <div className="grid grid-cols-2 gap-4 mb-6">
        <StatCard label="Total Chronic Spend" value={fmt(data.total_chronic_spend)} />
        <StatCard label="Members on Chronic" value={fmt(data.unique_members_on_chronic)} />
      </div>
      <DataTable exportName="chronic_meds" columns={[
        { key: 'drug', label: 'Drug / Description' },
        { key: 'total_spend', label: 'Total Spend', align: 'right', format: v => fmt(v) },
        { key: 'unique_members', label: 'Members', align: 'right', format: v => fmt(v) },
        { key: 'times_dispensed', label: 'Times Dispensed', align: 'right', format: v => fmt(v) },
      ]} data={data.data || []} />
    </>
  )
}

function SimulationTab({ data, discount, setDiscount, onRefresh }) {
  return (
    <>
      <div className="bg-white rounded-xl p-4 mb-6 shadow-sm flex items-end gap-4">
        <div>
          <label className="text-[10px] font-bold uppercase text-gray-400 block mb-1">Discount %</label>
          <input type="number" value={discount} onChange={e => setDiscount(e.target.value)} min="0" max="100"
                 className="w-24 px-3 py-2 border border-gray-200 rounded-lg text-sm" />
        </div>
        <button onClick={onRefresh} className="px-5 py-2 bg-lh-red text-white text-xs font-bold rounded-lg">Recalculate</button>
      </div>
      <div className="grid grid-cols-3 gap-4 mb-6">
        <StatCard label="Original Top 30 Total" value={fmt(data.original_top30_total)} />
        <StatCard label="Simulated Total" value={fmt(data.simulated_top30_total)} />
        <StatCard label="Estimated Saving" value={fmt(data.estimated_saving)} className="border-2 border-green-500" />
      </div>
      <DataTable exportName="simulation" columns={[
        { key: 'service', label: 'Service' },
        { key: 'original_spend', label: 'Original', align: 'right', format: v => fmt(v) },
        { key: 'simulated_spend', label: 'Simulated', align: 'right', format: v => fmt(v) },
        { key: 'saving', label: 'Saving', align: 'right', format: v => fmt(v) },
      ]} data={data.data || []} />
    </>
  )
}

function HighCostTab({ data, onRegenerate }) {
  return (
    <>
      <DataTable exportName="high_cost_cases" columns={[
        { key: 'claim_no', label: 'Claim No' },
        { key: 'enrolee_id', label: 'Enrolee ID' },
        { key: 'encounter_date', label: 'Date' },
        { key: 'diagnosis', label: 'Diagnosis' },
        { key: 'services', label: 'Services' },
        { key: 'total_paid', label: 'Total Paid', align: 'right', format: v => fmt(v) },
      ]} data={data.cases || []} />
      {data.ai_narrative && <AiCard narrative={data.ai_narrative} onRegenerate={onRegenerate} />}
    </>
  )
}

function BundlingTab({ data, onRegenerate }) {
  return (
    <>
      <div className="mb-4"><StatCard label="Total Flagged Claims" value={fmt(data.total_flagged)} /></div>
      <DataTable exportName="bundling_flags" columns={[
        { key: 'claim_no', label: 'Claim No' },
        { key: 'enrolee_id', label: 'Enrolee ID' },
        { key: 'date', label: 'Date' },
        { key: 'services', label: 'Services' },
        { key: 'total_paid', label: 'Total Paid', align: 'right', format: v => fmt(v) },
        { key: 'flag_type', label: 'Flag Type' },
        { key: 'flag_reason', label: 'Reason' },
      ]} data={data.flags || []} />
      {data.ai_narrative && <AiCard narrative={data.ai_narrative} onRegenerate={onRegenerate} />}
    </>
  )
}

function EnrolleeTab({ data }) {
  const rows = data.data || []
  return (
    <>
      {data.flagged_multi_provider?.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-4 text-sm text-red-700">
          ⚠ {data.flagged_multi_provider.length} enrollee(s) visited more than 5 distinct providers
        </div>
      )}
      <DataTable exportName="enrollees" columns={[
        { key: 'enrolee_id', label: 'Enrolee ID' },
        { key: 'family_id', label: 'Family ID' },
        { key: 'total_paid', label: 'Total Paid', align: 'right', format: v => fmt(v) },
        { key: 'hospitals_visited', label: 'Hospitals Visited' },
        { key: 'num_hospitals', label: '# Hospitals', align: 'right' },
        { key: 'num_visits', label: '# Visits', align: 'right' },
      ]} data={rows} />
    </>
  )
}

function AiCard({ narrative, onRegenerate }) {
  return (
    <div className="mt-6 bg-white rounded-xl border border-lh-navy/20 shadow-sm overflow-hidden">
      <div className="bg-lh-navy px-5 py-3 flex items-center justify-between">
        <span className="text-white text-xs font-bold">🤖 AI Analysis</span>
        <button onClick={onRegenerate} className="text-[10px] text-white/60 hover:text-white font-semibold">↻ Regenerate</button>
      </div>
      <div className="p-5 text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">{narrative}</div>
    </div>
  )
}

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
  { key: 'diagnosis', label: 'Diagnosis Patterns' },
  { key: 'frequency', label: 'Visit Frequency' },
  { key: 'simulation', label: 'Simulation' },
  { key: 'high-cost', label: 'High Cost Cases' },
  { key: 'bundling', label: 'Bundling Flags' },
  { key: 'enrollees', label: 'Enrollee Analysis' },
]

const REPORT_SECTIONS = [
  { key: 'overview', label: 'Overview' },
  { key: 'groups', label: 'Groups' },
  { key: 'schemes', label: 'Schemes' },
  { key: 'top30lines', label: 'Top 30 Tariff Lines' },
  { key: 'chronic', label: 'Chronic Medication' },
  { key: 'diagnosis', label: 'Diagnosis Patterns' },
  { key: 'enrollees', label: 'Enrollee Analysis' },
  { key: 'visitfrequency', label: 'Visit Frequency' },
]

export default function ProviderAnalytics({ session }) {
  const [tab, setTab] = useState('overview')
  const [provider, setProvider] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [discountPct, setDiscountPct] = useState(20)
  const [showExportModal, setShowExportModal] = useState(false)
  const [exportSections, setExportSections] = useState(
    Object.fromEntries(REPORT_SECTIONS.map(s => [s.key, true]))
  )

  const buildParams = useCallback(() => {
    const p = new URLSearchParams({ session_id: session.session_id })
    if (provider) p.append('provider_name', provider)
    if (dateFrom) p.append('date_from', dateFrom)
    if (dateTo) p.append('date_to', dateTo)
    return p
  }, [session.session_id, provider, dateFrom, dateTo])

  const fetchData = useCallback(async (t) => {
    setLoading(true); setData(null)
    const params = buildParams()
    let url = ''
    switch (t || tab) {
      case 'overview': url = `${API}/provider/overview`; break
      case 'groups': url = `${API}/provider/groups`; break
      case 'schemes': url = `${API}/provider/schemes`; break
      case 'top-lines': url = `${API}/provider/top-lines`; break
      case 'chronic': url = `${API}/provider/chronic`; break
      case 'diagnosis': url = `${API}/provider/diagnosis-patterns`; break
      case 'frequency': url = `${API}/provider/visit-frequency`; break
      case 'simulation': params.append('discount_pct', discountPct); url = `${API}/provider/simulate`; break
      case 'high-cost': url = `${API}/provider/high-cost-cases`; break
      case 'bundling': url = `${API}/provider/bundling-flags`; break
      case 'enrollees': url = `${API}/client/enrollees`; break
      default: url = `${API}/provider/overview`
    }
    try { const res = await fetch(`${url}?${params}`); setData(await res.json()) }
    catch { setData(null) }
    setLoading(false)
  }, [buildParams, tab, discountPct])

  useEffect(() => { fetchData() }, [tab])

  function handleApply(e) { e.preventDefault(); fetchData() }

  function handleExport() {
    const params = buildParams()
    const selected = Object.entries(exportSections).filter(([, v]) => v).map(([k]) => k)
    if (selected.length > 0) params.append('sections', selected.join(','))
    fetch(`${API}/provider/export-all?${params}`, { method: 'POST' })
      .then(r => r.blob()).then(b => {
        const a = document.createElement('a')
        a.href = URL.createObjectURL(b)
        a.download = `${(provider || 'All_Providers').replace(/ /g, '_')}_Analytics.xlsx`
        a.click(); setShowExportModal(false)
      })
  }

  function toggleSection(key) {
    setExportSections(prev => ({ ...prev, [key]: !prev[key] }))
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-extrabold text-lh-dark">Provider Analytics</h1>
          <p className="text-sm text-gray-400">Performance, cost, and utilisation deep dive</p>
        </div>
        <button onClick={() => setShowExportModal(true)}
                className="px-4 py-2 bg-lh-dark text-white text-xs font-bold rounded-lg hover:bg-lh-navy flex items-center gap-2">
          ⬇ Download Report
        </button>
      </div>

      {/* Export Modal */}
      {showExportModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setShowExportModal(false)}>
          <div className="bg-white rounded-2xl p-6 w-full max-w-md shadow-xl" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-extrabold text-lh-dark mb-1">Download Report</h3>
            <p className="text-xs text-gray-400 mb-4">Select sections to include in the Excel report</p>
            <div className="space-y-2 mb-6">
              {REPORT_SECTIONS.map(s => (
                <label key={s.key} className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-50 cursor-pointer">
                  <input type="checkbox" checked={exportSections[s.key]}
                         onChange={() => toggleSection(s.key)}
                         className="w-4 h-4 accent-lh-red rounded" />
                  <span className="text-sm font-medium text-lh-dark">{s.label}</span>
                </label>
              ))}
            </div>
            <div className="flex gap-3">
              <button onClick={handleExport}
                      className="flex-1 py-3 bg-lh-red text-white font-bold text-sm rounded-xl hover:bg-red-700">
                Download Excel
              </button>
              <button onClick={() => setShowExportModal(false)}
                      className="px-6 py-3 bg-gray-100 text-gray-600 font-semibold text-sm rounded-xl hover:bg-gray-200">
                Cancel
              </button>
            </div>
            <button onClick={() => setExportSections(Object.fromEntries(REPORT_SECTIONS.map(s => [s.key, true])))}
                    className="w-full mt-2 text-[10px] text-gray-400 hover:text-lh-red text-center">
              Select All
            </button>
          </div>
        </div>
      )}

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
          <label className="text-[10px] font-bold uppercase text-gray-400 block mb-1">From</label>
          <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
                 className="px-3 py-2 border border-gray-200 rounded-lg text-sm bg-gray-50 focus:border-lh-red focus:outline-none" />
        </div>
        <div>
          <label className="text-[10px] font-bold uppercase text-gray-400 block mb-1">To</label>
          <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
                 className="px-3 py-2 border border-gray-200 rounded-lg text-sm bg-gray-50 focus:border-lh-red focus:outline-none" />
        </div>
        <button type="submit" className="px-5 py-2 bg-lh-red text-white text-xs font-bold rounded-lg hover:bg-red-700">Apply</button>
      </form>

      {/* Sub tabs */}
      <div className="flex gap-1 mb-6 overflow-x-auto pb-1">
        {SUB_TABS.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
                  className={`px-3 py-2 rounded-lg text-[11px] font-semibold whitespace-nowrap transition-colors ${
                    tab === t.key ? 'bg-lh-dark text-white' : 'bg-white text-gray-500 hover:bg-gray-100'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {loading && <div className="text-center py-16 text-gray-400"><div className="text-3xl animate-pulse mb-2">⏳</div>Loading...</div>}

      {!loading && data && (
        <>
          {tab === 'overview' && <OverviewTab data={data} />}
          {tab === 'groups' && <GroupsTab data={data} />}
          {tab === 'schemes' && <SchemesTab data={data} />}
          {tab === 'top-lines' && <TopLinesTab data={data} />}
          {tab === 'chronic' && <ChronicTab data={data} />}
          {tab === 'diagnosis' && <DiagnosisTab data={data} />}
          {tab === 'frequency' && <FrequencyTab data={data} />}
          {tab === 'simulation' && <SimulationTab data={data} discount={discountPct} setDiscount={setDiscountPct} onRefresh={() => fetchData('simulation')} />}
          {tab === 'high-cost' && <HighCostTab data={data} onRegenerate={() => fetchData('high-cost')} />}
          {tab === 'bundling' && <BundlingTab data={data} onRegenerate={() => fetchData('bundling')} />}
          {tab === 'enrollees' && <EnrolleeTab data={data} />}
        </>
      )}
      {!loading && !data && <Empty />}
    </div>
  )
}

function Empty() {
  return <div className="text-center py-16 text-gray-400">No data. Select filters and click Apply.</div>
}

// ── TAB COMPONENTS ──

function OverviewTab({ data }) {
  const s = data.summary || {}
  return (
    <>
      <div className="grid grid-cols-5 gap-3 mb-6">
        <StatCard label="Total Spend" value={fmt(s.total_spend)} />
        <StatCard label="Unique Members" value={fmt(data.cumulative_unique_members)} />
        <StatCard label="Unique Visits" value={fmt(s.total_claims)} />
        <StatCard label="Avg / Visit" value={fmt(s.avg_per_visit)} />
        <StatCard label="Avg / Member" value={fmt(s.avg_per_member)} />
      </div>

      {/* OPD / IPD split */}
      {data.service_split?.length > 0 && (
        <div className="grid grid-cols-4 gap-3 mb-6">
          {data.service_split.map(s => (
            <div key={s.service_type} className="bg-white rounded-xl p-4 shadow-sm">
              <div className="text-[10px] font-bold uppercase text-gray-400">{s.service_type}</div>
              <div className="text-lg font-extrabold text-lh-dark">{fmt(s.amount_paid)}</div>
              <div className="text-xs text-gray-400">{s.pct}% of spend · {fmt(s.visits)} visits</div>
            </div>
          ))}
        </div>
      )}

      <DataTable exportName="overview" columns={[
        { key: 'month', label: 'Month' },
        { key: 'amount_paid', label: 'Amount Paid', align: 'right', format: v => fmt(v) },
        { key: 'unique_members', label: 'Members', align: 'right', format: v => fmt(v) },
        { key: 'unique_visits', label: 'Visits', align: 'right', format: v => fmt(v) },
        { key: 'avg_per_member', label: 'Avg/Member', align: 'right', format: v => fmt(v) },
        { key: 'avg_per_visit', label: 'Avg/Visit', align: 'right', format: v => fmt(v) },
        { key: 'mom_change', label: 'MoM %', align: 'right', format: v => v != null ? `${v > 0 ? '+' : ''}${v}%` : '—' },
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
    { key: 'per_member_cost', label: 'Per Member', align: 'right', format: v => fmt(v) },
    { key: 'pct_of_total', label: '% Total', align: 'right', format: v => `${v}%` },
  ]} data={data.data || []} />
}

function SchemesTab({ data }) {
  return <DataTable exportName="schemes" columns={[
    { key: 'scheme', label: 'Scheme' },
    { key: 'amount_paid', label: 'Amount Paid', align: 'right', format: v => fmt(v) },
    { key: 'unique_members', label: 'Members', align: 'right', format: v => fmt(v) },
    { key: 'unique_visits', label: 'Visits', align: 'right', format: v => fmt(v) },
    { key: 'per_member_cost', label: 'Per Member', align: 'right', format: v => fmt(v) },
    { key: 'pct_of_total', label: '% Total', align: 'right', format: v => `${v}%` },
  ]} data={data.data || []} />
}

function TopLinesTab({ data }) {
  return (
    <>
      {data.total_all_lines > 0 && <div className="mb-4"><StatCard label="Total All Lines" value={fmt(data.total_all_lines)} /></div>}
      <DataTable exportName="top30_lines" columns={[
        { key: 'rank', label: '#', align: 'right' },
        { key: 'service', label: 'Service' },
        { key: 'amount_paid', label: 'Amount Paid', align: 'right', format: v => fmt(v) },
        { key: 'times_utilized', label: 'Utilized', align: 'right', format: v => fmt(v) },
        { key: 'unique_members', label: 'Members', align: 'right', format: v => fmt(v) },
        { key: 'avg_paid_per_line', label: 'Avg/Line', align: 'right', format: v => fmt(v) },
        { key: 'pct_of_total', label: '% Total', align: 'right', format: v => `${v}%` },
        { key: 'cumulative_pct', label: 'Cum %', align: 'right', format: v => `${v}%` },
      ]} data={data.data || []} />
    </>
  )
}

function ChronicTab({ data }) {
  return (
    <>
      <div className="grid grid-cols-3 gap-4 mb-6">
        <StatCard label="Chronic Spend" value={fmt(data.total_chronic_spend)} />
        <StatCard label="Members on Chronic" value={fmt(data.unique_members_on_chronic)} />
        <StatCard label="% of Total Spend" value={`${data.pct_of_total_spend || 0}%`} />
      </div>
      <DataTable exportName="chronic_meds" columns={[
        { key: 'drug', label: 'Drug / Description' },
        { key: 'total_spend', label: 'Total Spend', align: 'right', format: v => fmt(v) },
        { key: 'unique_members', label: 'Members', align: 'right', format: v => fmt(v) },
        { key: 'times_dispensed', label: 'Dispensed', align: 'right', format: v => fmt(v) },
        { key: 'avg_per_dispense', label: 'Avg/Dispense', align: 'right', format: v => fmt(v) },
      ]} data={data.data || []} />
    </>
  )
}

function DiagnosisTab({ data }) {
  return (
    <>
      <div className="grid grid-cols-2 gap-4 mb-6">
        <StatCard label="Vague Diagnosis Spend" value={fmt(data.total_vague_spend)} className={data.pct_vague > 15 ? 'border-2 border-red-400' : ''} />
        <StatCard label="% Spend on Vague Diagnoses" value={`${data.pct_vague || 0}%`} className={data.pct_vague > 15 ? 'border-2 border-red-400' : ''} />
      </div>
      {data.pct_vague > 15 && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-4 text-sm text-red-700">
          ⚠ <strong>{data.pct_vague}%</strong> of spend is on vague/unspecified diagnoses — this is a red flag for potential upcoding or poor documentation.
        </div>
      )}
      <DataTable exportName="diagnosis_patterns" columns={[
        { key: 'diagnosis', label: 'Diagnosis' },
        { key: 'amount_paid', label: 'Amount Paid', align: 'right', format: v => fmt(v) },
        { key: 'unique_members', label: 'Members', align: 'right', format: v => fmt(v) },
        { key: 'unique_visits', label: 'Visits', align: 'right', format: v => fmt(v) },
        { key: 'pct_of_total', label: '% Total', align: 'right', format: v => `${v}%` },
        { key: 'vague_flag', label: 'Vague?', format: v => v ? '⚠️' : '' },
      ]} data={data.data || []} />
    </>
  )
}

function FrequencyTab({ data }) {
  return (
    <>
      {/* Day of week */}
      {data.day_of_week?.length > 0 && (
        <div className="bg-white rounded-xl p-5 shadow-sm mb-6">
          <h4 className="text-xs font-bold uppercase text-gray-400 mb-3">Visits by Day of Week</h4>
          <div className="flex gap-2 items-end h-24">
            {data.day_of_week.map(d => {
              const max = Math.max(...data.day_of_week.map(x => x.visits), 1)
              return (
                <div key={d.day} className="flex-1 flex flex-col items-center">
                  <div className="text-[10px] font-bold text-lh-dark mb-1">{d.visits}</div>
                  <div className="w-full bg-lh-red/80 rounded-t" style={{ height: `${(d.visits / max) * 80}px` }} />
                  <div className="text-[9px] text-gray-400 mt-1">{d.day.slice(0, 3)}</div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* High frequency members */}
      <h4 className="text-sm font-bold text-lh-dark mb-3">Members with 4+ visits in a single month</h4>
      {data.high_frequency_members?.length > 0 ? (
        <DataTable exportName="visit_frequency" columns={[
          { key: 'enrolee_id', label: 'Enrolee ID' },
          { key: 'month', label: 'Month' },
          { key: 'visit_count', label: 'Visits', align: 'right' },
          ...(data.high_frequency_members[0]?.provider ? [{ key: 'provider', label: 'Provider' }] : []),
        ]} data={data.high_frequency_members} />
      ) : <div className="text-center py-8 text-gray-400 text-sm">No members with 4+ visits in a single month.</div>}
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
        <StatCard label="Original Top 30" value={fmt(data.original_top30_total)} />
        <StatCard label="After Discount" value={fmt(data.simulated_top30_total)} />
        <StatCard label="Estimated Saving" value={fmt(data.estimated_saving)} className="border-2 border-green-500" />
      </div>
      <DataTable exportName="simulation" columns={[
        { key: 'service', label: 'Service' },
        { key: 'original_spend', label: 'Original', align: 'right', format: v => fmt(v) },
        { key: 'simulated_spend', label: 'After Discount', align: 'right', format: v => fmt(v) },
        { key: 'saving', label: 'Saving', align: 'right', format: v => fmt(v) },
        { key: 'discounted', label: 'Applied', format: v => v ? '✓' : '—' },
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
        { key: 'total_paid', label: 'Visit Cost', align: 'right', format: v => fmt(v) },
        { key: 'member_total_spend', label: 'Member Total', align: 'right', format: v => fmt(v) },
        { key: 'member_total_visits', label: 'Member Visits', align: 'right' },
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
  return (
    <>
      {data.top_spenders?.length > 0 && (
        <div className="bg-orange-50 border border-orange-200 rounded-xl p-4 mb-4 text-sm text-orange-700">
          🔝 <strong>Top 10 spenders</strong> flagged in the table below
        </div>
      )}
      {data.flagged_multi_provider?.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-4 text-sm text-red-700">
          ⚠ {data.flagged_multi_provider.length} enrollee(s) visited more than 5 distinct providers
        </div>
      )}

      {/* Family subtotals */}
      {data.families?.length > 0 && (
        <div className="bg-white rounded-xl p-5 shadow-sm mb-6">
          <h4 className="text-xs font-bold uppercase text-gray-400 mb-3">Family Units (Multi-member)</h4>
          <DataTable exportName="families" columns={[
            { key: 'family_id', label: 'Family ID' },
            { key: 'member_count', label: 'Members', align: 'right' },
            { key: 'total_paid', label: 'Family Total', align: 'right', format: v => fmt(v) },
            { key: 'total_visits', label: 'Total Visits', align: 'right' },
          ]} data={data.families} pageSize={20} />
        </div>
      )}

      <DataTable exportName="enrollees" columns={[
        { key: 'enrolee_id', label: 'Enrolee ID' },
        { key: 'family_id', label: 'Family ID' },
        { key: 'total_paid', label: 'Total Paid', align: 'right', format: v => fmt(v) },
        { key: 'hospitals_visited', label: 'Hospitals' },
        { key: 'num_hospitals', label: '# Hospitals', align: 'right' },
        { key: 'num_visits', label: '# Visits', align: 'right' },
        { key: 'top_spender', label: 'Top 10?', format: v => v ? '🔝' : '' },
        { key: 'multi_provider_flag', label: 'Flag', format: v => v ? '⚠️' : '' },
      ]} data={data.data || []} />
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

import StatCard from '../components/StatCard'

export default function ProviderAnalytics({ session }) {
  const fmt = n => n ? Number(n).toLocaleString() : '0'

  return (
    <div>
      <h1 className="text-2xl font-extrabold text-lh-dark mb-1">Provider Analytics</h1>
      <p className="text-sm text-gray-400 mb-6">Performance scoring, cost benchmarking, and network utilisation</p>

      <div className="grid grid-cols-4 gap-4 mb-8">
        <StatCard label="Total Spend" value={fmt(Math.round(session.total_spend))} />
        <StatCard label="Unique Providers" value={fmt(session.unique_providers_count)} />
        <StatCard label="Unique Members" value={fmt(session.unique_members)} />
        <StatCard label="Total Claims" value={fmt(session.row_count)} />
      </div>

      <div className="bg-white rounded-2xl p-8 shadow-sm text-center text-gray-400">
        <div className="text-4xl mb-3">📊</div>
        <p className="font-semibold text-lh-dark">Provider Analytics module</p>
        <p className="text-sm mt-1">Detailed provider analysis coming soon</p>
      </div>
    </div>
  )
}

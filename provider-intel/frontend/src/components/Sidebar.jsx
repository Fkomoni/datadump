import { NavLink } from 'react-router-dom'

const modules = [
  { path: '/provider-analytics', label: 'Provider Analytics', icon: '📊' },
  { path: '/tariff-intelligence', label: 'Tariff Intelligence', icon: '💰' },
  { path: '/fwa-insights', label: 'FWA Insights', icon: '🚨' },
  { path: '/tariff-mapper', label: 'Tariff Mapper', icon: '🗂️' },
  { path: '/plan-access', label: 'Plan Access', icon: '🔐' },
]

export default function Sidebar({ session, onReset }) {
  return (
    <aside className="w-64 bg-lh-dark text-white flex flex-col h-full flex-shrink-0">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-white/10">
        <div className="text-sm font-bold tracking-wide opacity-50">LEADWAY HEALTH</div>
        <div className="text-base font-extrabold mt-1">Provider Intelligence</div>
      </div>

      {/* Session info */}
      <div className="px-5 py-4 border-b border-white/10 text-xs">
        <div className="opacity-50 mb-1">Session</div>
        <div className="font-semibold truncate">{session.filename}</div>
        <div className="opacity-50 mt-1">{session.row_count.toLocaleString()} rows</div>
        {session.date_range && (
          <div className="opacity-50">{session.date_range.from} — {session.date_range.to}</div>
        )}
        <div className="opacity-50">{session.unique_members.toLocaleString()} members · {session.unique_providers_count} providers</div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4">
        {modules.map(m => (
          <NavLink
            key={m.path}
            to={m.path}
            className={({ isActive }) =>
              `flex items-center gap-3 px-5 py-3 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-white/10 text-white border-r-2 border-lh-red'
                  : 'text-white/60 hover:text-white hover:bg-white/5'
              }`
            }
          >
            <span className="text-base">{m.icon}</span>
            {m.label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-white/10">
        <button
          onClick={onReset}
          className="w-full text-xs text-white/40 hover:text-white/80 transition-colors text-left"
        >
          ↩ Upload new file
        </button>
      </div>
    </aside>
  )
}

export default function StatCard({ label, value, trend, className = '' }) {
  return (
    <div className={`bg-white rounded-xl p-5 shadow-sm ${className}`}>
      <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-1">{label}</div>
      <div className="text-2xl font-extrabold text-lh-dark">{value}</div>
      {trend && (
        <div className={`text-xs font-semibold mt-1 ${trend > 0 ? 'text-red-500' : 'text-green-600'}`}>
          {trend > 0 ? '▲' : '▼'} {Math.abs(trend)}%
        </div>
      )}
    </div>
  )
}

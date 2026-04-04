export default function TariffMapper({ session }) {
  return (
    <div>
      <h1 className="text-2xl font-extrabold text-lh-dark mb-1">Tariff Mapper</h1>
      <p className="text-sm text-gray-400 mb-6">Session: {session.filename} · {session.row_count.toLocaleString()} rows</p>

      <div className="bg-white rounded-2xl p-8 shadow-sm text-center text-gray-400">
        <div className="text-4xl mb-3">🗂️</div>
        <p className="font-semibold text-lh-dark">Tariff Mapper</p>
        <p className="text-sm mt-1">Module coming soon</p>
      </div>
    </div>
  )
}

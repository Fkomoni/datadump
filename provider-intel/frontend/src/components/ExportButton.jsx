export default function ExportButton({ label = 'Export', onClick }) {
  return (
    <button
      onClick={onClick}
      className="inline-flex items-center gap-1.5 px-4 py-2 bg-lh-dark text-white text-xs font-bold rounded-lg hover:bg-lh-navy transition-colors"
    >
      <span>⬇</span> {label}
    </button>
  )
}

import { useState, useRef } from 'react'

export default function FileUpload({ onUpload }) {
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)
  const fileRef = useRef()

  async function handleFile(file) {
    if (!file) return
    setUploading(true)
    setError(null)
    const form = new FormData()
    form.append('file', file)

    try {
      const res = await fetch('/api/upload', { method: 'POST', body: form })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || 'Upload failed')
      }
      const data = await res.json()
      onUpload(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="min-h-screen bg-lh-cream flex items-center justify-center p-6">
      <div className="w-full max-w-lg">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="text-xs font-bold tracking-widest text-lh-red uppercase mb-2">Leadway Health</div>
          <h1 className="text-3xl font-extrabold text-lh-dark">Provider Intelligence</h1>
          <p className="text-sm text-gray-500 mt-2">Upload a claims file to begin analysis</p>
        </div>

        {/* Upload area */}
        <div
          className={`bg-white rounded-2xl p-10 border-2 border-dashed transition-colors cursor-pointer ${
            dragging ? 'border-lh-red bg-red-50' : 'border-gray-300 hover:border-lh-navy'
          }`}
          onDragOver={e => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={e => { e.preventDefault(); setDragging(false); handleFile(e.dataTransfer.files[0]) }}
          onClick={() => fileRef.current?.click()}
        >
          <input
            ref={fileRef}
            type="file"
            accept=".xlsx,.xls,.csv"
            className="hidden"
            onChange={e => handleFile(e.target.files[0])}
          />
          <div className="text-center">
            {uploading ? (
              <>
                <div className="text-4xl mb-4 animate-pulse">⏳</div>
                <p className="text-sm font-semibold text-lh-dark">Processing file...</p>
                <p className="text-xs text-gray-400 mt-1">Detecting columns and parsing data</p>
              </>
            ) : (
              <>
                <div className="text-4xl mb-4">📁</div>
                <p className="text-sm font-semibold text-lh-dark">Drop your claims file here</p>
                <p className="text-xs text-gray-400 mt-1">or click to browse — .xlsx, .xls, .csv</p>
              </>
            )}
          </div>
        </div>

        {error && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Info cards */}
        <div className="grid grid-cols-3 gap-3 mt-6">
          {[
            { icon: '📊', label: 'Provider Analytics' },
            { icon: '💰', label: 'Tariff Intelligence' },
            { icon: '🚨', label: 'FWA Detection' },
          ].map(m => (
            <div key={m.label} className="bg-white rounded-xl p-4 text-center shadow-sm">
              <div className="text-xl mb-1">{m.icon}</div>
              <div className="text-[10px] font-bold text-gray-500 uppercase">{m.label}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

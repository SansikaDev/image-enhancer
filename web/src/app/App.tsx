import React, { useMemo, useState } from 'react'

const API_BASE = (import.meta as any).env?.VITE_API_BASE || 'http://localhost:8000'

function dataUrlToBlob(dataUrl: string): Blob {
  const [header, base64] = dataUrl.split(',')
  const mimeMatch = header.match(/data:(.*);base64/)
  const mime = mimeMatch ? mimeMatch[1] : 'application/octet-stream'
  const bytes = atob(base64)
  const buf = new Uint8Array(bytes.length)
  for (let i = 0; i < bytes.length; i++) buf[i] = bytes.charCodeAt(i)
  return new Blob([buf], { type: mime })
}

export default function App() {
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [scale, setScale] = useState<number>(2)
  const [width, setWidth] = useState<string>('')
  const [height, setHeight] = useState<string>('')
  const [denoiseLuma, setDenoiseLuma] = useState(5)
  const [denoiseColor, setDenoiseColor] = useState(5)
  const [claheClip, setClaheClip] = useState(2.0)
  const [sharpenAmount, setSharpenAmount] = useState(0.6)
  const [sharpenSigma, setSharpenSigma] = useState(1.2)
  const [saturation, setSaturation] = useState(1.05)

  const [result, setResult] = useState<{
    png?: string
    jpg?: string
    webp?: string
    apng?: string
  } | null>(null)

  const canSubmit = !!file && !busy

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!file) return
    setBusy(true)
    setError(null)
    setResult(null)

    const form = new FormData()
    form.append('file', file)

    if (width || height) {
      if (width) form.append('width', String(parseInt(width)))
      if (height) form.append('height', String(parseInt(height)))
    } else {
      form.append('scale', String(scale))
    }

    form.append('denoise_luma', String(denoiseLuma))
    form.append('denoise_color', String(denoiseColor))
    form.append('clahe_clip', String(claheClip))
    form.append('sharpen_amount', String(sharpenAmount))
    form.append('sharpen_sigma', String(sharpenSigma))
    form.append('saturation', String(saturation))

    try {
      const res = await fetch(`${API_BASE}/api/enhance`, { method: 'POST', body: form })
      if (!res.ok) throw new Error(`API error: ${res.status}`)
      const data = await res.json()
      setResult(data)
    } catch (err: any) {
      setError(err?.message || 'Unknown error')
    } finally {
      setBusy(false)
    }
  }

  function DownloadButton({ label, dataUrl, filename }: { label: string, dataUrl?: string, filename: string }) {
    if (!dataUrl) return null
    const blob = useMemo(() => dataUrlToBlob(dataUrl), [dataUrl])
    const href = useMemo(() => URL.createObjectURL(blob), [blob])
    return (
      <a href={href} download={filename}>
        <button type="button">Download {label}</button>
      </a>
    )
  }

  return (
    <div className="container">
      <h1>Image Enhancer</h1>
      <div className="card">
        <form onSubmit={onSubmit} className="row">
          <div style={{flex: '1 1 280px'}}>
            <label>Image</label>
            <input type="file" accept="image/*" onChange={e => setFile(e.target.files?.[0] || null)} />
            <div className="small">PNG, JPG, etc.</div>
          </div>

          <div style={{flex: '1 1 160px'}}>
            <label>Scale (x)</label>
            <input type="number" step="0.1" value={scale} onChange={e => setScale(parseFloat(e.target.value))} disabled={!!(width || height)} />
            <div className="small">Ignored if width/height set</div>
          </div>

          <div style={{flex: '1 1 120px'}}>
            <label>Target Width</label>
            <input type="number" min="1" value={width} onChange={e => setWidth(e.target.value)} />
          </div>

          <div style={{flex: '1 1 120px'}}>
            <label>Target Height</label>
            <input type="number" min="1" value={height} onChange={e => setHeight(e.target.value)} />
          </div>

          <div style={{flex: '1 1 120px'}}>
            <label>Denoise Luma</label>
            <input type="number" min="0" max="20" value={denoiseLuma} onChange={e => setDenoiseLuma(parseInt(e.target.value))} />
          </div>

          <div style={{flex: '1 1 120px'}}>
            <label>Denoise Color</label>
            <input type="number" min="0" max="20" value={denoiseColor} onChange={e => setDenoiseColor(parseInt(e.target.value))} />
          </div>

          <div style={{flex: '1 1 120px'}}>
            <label>CLAHE Clip</label>
            <input type="number" step="0.1" min="0.5" max="5" value={claheClip} onChange={e => setClaheClip(parseFloat(e.target.value))} />
          </div>

          <div style={{flex: '1 1 120px'}}>
            <label>Sharpen Amount</label>
            <input type="number" step="0.1" min="0" max="2" value={sharpenAmount} onChange={e => setSharpenAmount(parseFloat(e.target.value))} />
          </div>

          <div style={{flex: '1 1 120px'}}>
            <label>Sharpen Sigma</label>
            <input type="number" step="0.1" min="0.1" max="3" value={sharpenSigma} onChange={e => setSharpenSigma(parseFloat(e.target.value))} />
          </div>

          <div style={{flex: '1 1 120px'}}>
            <label>Saturation</label>
            <input type="number" step="0.01" min="0" max="2" value={saturation} onChange={e => setSaturation(parseFloat(e.target.value))} />
          </div>

          <div style={{alignSelf: 'end'}}>
            <button type="submit" disabled={!canSubmit}>{busy ? 'Enhancing…' : 'Enhance'}</button>
          </div>
        </form>
      </div>

      {error && <p style={{color: 'red'}}>{error}</p>}

      {result && (
        <div className="card" style={{marginTop: 16}}>
          <h2>Result</h2>
          {result.png && <img className="preview" src={result.png} alt="Preview" />}
          <div className="row" style={{marginTop: 12}}>
            <DownloadButton label="PNG" dataUrl={result.png} filename="image_enhanced.png" />
            <DownloadButton label="JPG" dataUrl={result.jpg} filename="image_enhanced.jpg" />
            <DownloadButton label="WEBP" dataUrl={result.webp} filename="image_enhanced.webp" />
            <DownloadButton label="APNG" dataUrl={result.apng} filename="image_enhanced.apng" />
          </div>
        </div>
      )}
    </div>
  )
}

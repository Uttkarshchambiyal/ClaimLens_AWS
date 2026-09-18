import { useEffect, useRef, useState } from 'react'
import {
  FileSearch,
  FileText,
  Maximize2,
  Minus,
  Plus,
  X,
  PencilLine,
  Loader2,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import { appMode, getDocumentSource } from '../api'
import type { Analysis, EvidenceRef } from '../types'

function PdfPage({
  url,
  page,
  onError,
}: {
  url: string
  page: number
  onError: (s: string) => void
}) {
  const canvas = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    let cancelled = false
    let destroy: (() => void) | undefined
    const render = async () => {
      try {
        const pdfjs = await import('pdfjs-dist')
        pdfjs.GlobalWorkerOptions.workerSrc = new URL(
          'pdfjs-dist/build/pdf.worker.min.mjs',
          import.meta.url,
        ).toString()
        const task = pdfjs.getDocument({ url })
        destroy = () => {
          void task.destroy()
        }
        const pdf = await task.promise
        if (cancelled) return
        const documentPage = await pdf.getPage(page)
        if (cancelled || !canvas.current) return
        const viewport = documentPage.getViewport({ scale: 1.5 })
        const target = canvas.current
        target.width = viewport.width
        target.height = viewport.height
        await documentPage.render({ canvas: target, viewport }).promise
      } catch {
        if (!cancelled)
          onError(
            'This page could not be rendered. Reopen the document to refresh its access link.',
          )
      }
    }
    void render()
    return () => {
      cancelled = true
      destroy?.()
    }
  }, [url, page, onError])
  return (
    <canvas ref={canvas} className="pdf-canvas" aria-label={'Original document, page ' + page} />
  )
}

export function SourceViewer({
  analysis,
  evidence,
  token,
  onClose,
  onCorrect,
}: {
  analysis: Analysis
  evidence?: EvidenceRef
  token?: string
  onClose: () => void
  onCorrect: (value: string) => Promise<void>
}) {
  const panel = useRef<HTMLElement>(null)
  const closeRef = useRef(onClose)
  closeRef.current = onClose
  const [zoom, setZoom] = useState(100)
  const [page, setPage] = useState(evidence?.page || 1)
  const [source, setSource] = useState<{ downloadUrl: string; contentType: string }>()
  const [error, setError] = useState('')
  const [saveError, setSaveError] = useState('')
  const [sourceAttempt, setSourceAttempt] = useState(0)
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState('')
  const [saving, setSaving] = useState(false)
  const [overlay, setOverlay] = useState(() => window.innerWidth < 1450)
  const doc = analysis.documents.find((d) => d.id === evidence?.documentId)
  useEffect(() => {
    const resize = () => setOverlay(window.innerWidth < 1450)
    window.addEventListener('resize', resize)
    return () => window.removeEventListener('resize', resize)
  }, [])
  useEffect(() => {
    if (!overlay) return
    const previous = document.activeElement as HTMLElement | null
    panel.current?.querySelector<HTMLButtonElement>('button')?.focus()
    const trap = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        closeRef.current()
        return
      }
      if (event.key !== 'Tab') return
      const elements = panel.current?.querySelectorAll<HTMLElement>(
        'button:not(:disabled), input, summary, a[href], select',
      )
      if (!elements?.length) return
      const first = elements[0],
        last = elements[elements.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', trap)
    return () => {
      document.removeEventListener('keydown', trap)
      if (previous?.isConnected) previous.focus()
      else document.getElementById('review-findings-tab')?.focus()
    }
  }, [overlay])
  useEffect(() => {
    setPage(evidence?.page || 1)
    setEditing(false)
    setValue('')
    setError('')
    setSaveError('')
  }, [evidence?.evidenceId])
  useEffect(() => {
    setSource(undefined)
    setError('')
    if (appMode === 'mock' || !evidence) return
    let active = true
    getDocumentSource(analysis.claimId, evidence.documentId, token)
      .then((result) => {
        if (active) setSource(result)
      })
      .catch((e) => {
        if (active) setError(e.message)
      })
    return () => {
      active = false
    }
  }, [analysis.claimId, evidence?.documentId, token, sourceAttempt])
  const save = async () => {
    setSaving(true)
    setSaveError('')
    try {
      await onCorrect(value)
      setEditing(false)
      setValue('')
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : 'Correction could not be saved.')
    } finally {
      setSaving(false)
    }
  }
  const refs = [
    ...new Map(
      analysis.findings
        .flatMap((f) => f.evidence)
        .filter((e) => e.documentId === evidence?.documentId && e.page === page)
        .map((e) => [e.evidenceId, e]),
    ).values(),
  ]
  return (
    <aside
      ref={panel}
      className="source-viewer"
      role={overlay ? 'dialog' : 'complementary'}
      aria-modal={overlay ? true : undefined}
      aria-label="Document source viewer"
    >
      <header className="panel-header">
        <div>
          <span className="eyebrow">Document evidence</span>
          <h3>Source viewer</h3>
        </div>
        <button className="icon-button" onClick={onClose} aria-label="Close source viewer">
          <X size={18} />
        </button>
      </header>
      {evidence ? (
        <>
          <div className="source-filename">
            <FileText size={17} />
            <span title={doc?.name || evidence.documentName}>
              {doc?.name || evidence.documentName}
            </span>
            <small>v{evidence.documentVersion || doc?.version || 1}</small>
          </div>
          <div className="viewer-controls">
            <div>
              <button
                className="icon-button"
                aria-label="Previous page"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                <ChevronLeft size={15} />
              </button>
              <span>
                {page} / {Math.max(doc?.pages || 1, evidence.page)}
              </span>
              <button
                className="icon-button"
                aria-label="Next page"
                disabled={page >= Math.max(doc?.pages || 1, evidence.page)}
                onClick={() => setPage((p) => p + 1)}
              >
                <ChevronRight size={15} />
              </button>
            </div>
            <div>
              <button
                className="icon-button"
                aria-label="Zoom out"
                disabled={zoom <= 75}
                onClick={() => setZoom((z) => z - 25)}
              >
                <Minus size={15} />
              </button>
              <span>{zoom}%</span>
              <button
                className="icon-button"
                aria-label="Zoom in"
                disabled={zoom >= 175}
                onClick={() => setZoom((z) => z + 25)}
              >
                <Plus size={15} />
              </button>
              <button className="icon-button" aria-label="Reset zoom" onClick={() => setZoom(100)}>
                <Maximize2 size={14} />
              </button>
            </div>
          </div>
          {appMode === 'mock' && (
            <div className="viewer-notice">Synthetic evidence sheet · not an uploaded PDF</div>
          )}
          <div className="document-stage">
            {error ? (
              <div className="empty-state compact" role="alert">
                <FileSearch />
                <p>{error}</p>
                <button
                  className="button secondary small"
                  onClick={() => setSourceAttempt((value) => value + 1)}
                >
                  Retry source
                </button>
              </div>
            ) : appMode !== 'mock' && !source ? (
              <div className="empty-state compact">
                <Loader2 className="spin" />
                <p>Loading private source…</p>
              </div>
            ) : (
              <div className="document-sheet" style={{ width: zoom + '%' }}>
                {appMode === 'mock' ? (
                  <div className="synthetic-sheet">
                    <div className="sheet-letterhead">
                      <strong>CLAIMLENS</strong>
                      <span>SYNTHETIC DOCUMENT</span>
                    </div>
                    <h4>
                      {doc?.type === 'BILL'
                        ? 'Itemized hospital bill'
                        : doc?.type === 'DISCHARGE_SUMMARY'
                          ? 'Discharge summary'
                          : 'Supporting report'}
                    </h4>
                    <p className="sheet-meta">
                      {analysis.claimId} · Page {page} · Fictional data
                    </p>
                    <div className="sheet-divider" />
                    {refs.length ? (
                      refs.map((ref) => (
                        <div
                          className={
                            'sheet-entry ' +
                            (ref.evidenceId === evidence.evidenceId ? 'sheet-entry-highlight' : '')
                          }
                          key={ref.evidenceId}
                        >
                          <small>Source block {ref.blockIds.join(', ')}</small>
                          <p>{ref.excerpt}</p>
                        </div>
                      ))
                    ) : (
                      <p className="sheet-meta">No cited excerpts on this page.</p>
                    )}
                    <div className="sheet-footer">
                      Evidence excerpts for demonstration only.
                      <br />
                      Source coordinates are shown below; this sheet is not a page facsimile.
                    </div>
                  </div>
                ) : (
                  <div className="original-page">
                    {source?.contentType === 'application/pdf' ? (
                      <PdfPage url={source.downloadUrl} page={page} onError={setError} />
                    ) : (
                      <img
                        src={source?.downloadUrl}
                        alt="Original source document"
                        onError={() => setError('Source image could not be loaded.')}
                      />
                    )}
                    {page === evidence.page && (
                      <div
                        className="geometry-highlight"
                        aria-label="Cited source region"
                        style={{
                          left: evidence.geometry.left * 100 + '%',
                          top: evidence.geometry.top * 100 + '%',
                          width: evidence.geometry.width * 100 + '%',
                          height: evidence.geometry.height * 100 + '%',
                        }}
                      />
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
          <div className="source-inspector">
            <div className="inspector-heading">
              <span className="eyebrow">Selected extraction</span>
              <span className="confidence">{evidence.confidence.toFixed(1)}% confidence</span>
            </div>
            <blockquote>{evidence.excerpt}</blockquote>
            <details>
              <summary>Source references & coordinates</summary>
              <dl>
                <dt>Evidence</dt>
                <dd>{evidence.evidenceId}</dd>
                <dt>Blocks</dt>
                <dd>{evidence.blockIds.join(', ')}</dd>
                <dt>Page region</dt>
                <dd>
                  {Object.entries(evidence.geometry)
                    .map(([k, v]) => k + ' ' + v.toFixed(3))
                    .join(' · ')}
                </dd>
              </dl>
            </details>
            {analysis.corrections
              ?.filter((c) => c.fieldId === evidence.evidenceId)
              .map((c) => (
                <div className="saved-correction" key={c.correctionId}>
                  <strong>Reviewer correction</strong>
                  <span>{c.correctedValue}</span>
                  <small>
                    Original preserved · checks not rerun
                    {c.actorId ? ' · Reviewer ' + c.actorId : ''}
                  </small>
                </div>
              ))}
            {editing ? (
              <div className="correction-form">
                <label htmlFor="correction">Corrected value</label>
                <input
                  id="correction"
                  autoFocus
                  disabled={saving}
                  value={value}
                  maxLength={500}
                  onChange={(e) => setValue(e.target.value)}
                />
                <small>
                  This adds a review annotation. Existing check results remain unchanged.
                </small>
                {saveError && (
                  <p className="form-error" role="alert">
                    {saveError}
                  </p>
                )}
                <div>
                  <button
                    className="button secondary small"
                    disabled={saving}
                    onClick={() => setEditing(false)}
                  >
                    Cancel
                  </button>
                  <button
                    className="button primary small"
                    disabled={!value.trim() || saving}
                    onClick={save}
                  >
                    {saving ? 'Saving…' : 'Save correction'}
                  </button>
                </div>
              </div>
            ) : (
              <button className="text-button" onClick={() => setEditing(true)}>
                <PencilLine size={15} />
                Correct extraction
              </button>
            )}
          </div>
        </>
      ) : (
        <div className="empty-state">
          <FileSearch size={32} />
          <h3>Follow the evidence</h3>
          <p>Select a cited passage to inspect its source document and extraction details.</p>
        </div>
      )}
    </aside>
  )
}

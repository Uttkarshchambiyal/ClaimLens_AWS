import { useEffect, useRef, useState } from 'react'
import { FileText, UploadCloud, X, Trash2, Loader2 } from 'lucide-react'
import { appMode, validateUploads } from '../api'
import type { UploadFile, UploadProgress } from '../types'

export function UploadDialog({
  onClose,
  onStart,
}: {
  onClose: () => void
  onStart: (
    files: UploadFile[],
    key: string,
    progress: (p: UploadProgress) => void,
  ) => Promise<void>
}) {
  const dialog = useRef<HTMLDialogElement>(null)
  const input = useRef<HTMLInputElement>(null)
  const key = useRef(crypto.randomUUID())
  const [files, setFiles] = useState<UploadFile[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)
  const [progress, setProgress] = useState<UploadProgress>()
  useEffect(() => {
    dialog.current?.showModal()
  }, [])
  const addFiles = (items: FileList | File[]) => {
    setError('')
    key.current = crypto.randomUUID()
    setFiles((current) => [
      ...current,
      ...Array.from(items).map((file, index) => ({
        file,
        type: current.length + index === 0 ? ('BILL' as const) : ('SUPPORTING_REPORT' as const),
      })),
    ])
  }
  const submit = async () => {
    const invalid = validateUploads(files)
    if (invalid) {
      setError(invalid)
      return
    }
    setBusy(true)
    setError('')
    try {
      await onStart(files, key.current, setProgress)
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed. Please retry.')
    } finally {
      setBusy(false)
    }
  }
  return (
    <dialog
      ref={dialog}
      className="upload-dialog"
      aria-labelledby="upload-title"
      onCancel={(event) => {
        event.preventDefault()
        if (!busy) onClose()
      }}
    >
      <div className="dialog-heading">
        <div className="dialog-icon">
          <UploadCloud size={24} />
        </div>
        <button className="icon-button" onClick={onClose} disabled={busy} aria-label="Close upload">
          <X size={20} />
        </button>
      </div>
      <h2 id="upload-title">Start a new review</h2>
      <p className="muted">
        Add an itemized bill and its supporting documents. Assign each document a type before
        starting.
      </p>
      {appMode === 'mock' && (
        <div className="inline-note">
          Mock mode: files stay on your device and are not extracted. Open a sample packet from the
          queue for a complete demonstration.
        </div>
      )}
      <input
        ref={input}
        type="file"
        aria-label="Claim documents"
        hidden
        multiple
        accept=".pdf,.png,.jpg,.jpeg"
        onChange={(e) => {
          if (e.target.files) addFiles(e.target.files)
          e.target.value = ''
        }}
      />
      <button
        className={'dropzone ' + (dragging ? 'dragging' : '')}
        disabled={busy}
        onClick={() => input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          if (!busy) addFiles(e.dataTransfer.files)
        }}
      >
        <UploadCloud size={30} />
        <strong>Drop documents here, or browse</strong>
        <span>PDF, PNG or JPEG · up to 15 MB each · 10 files maximum</span>
      </button>
      <div className="upload-files">
        {files.map((item, index) => (
          <div className="upload-file" key={index}>
            <FileText size={20} />
            <div>
              <strong>{item.file.name}</strong>
              <small>{(item.file.size / 1024).toFixed(0)} KB</small>
            </div>
            <select
              aria-label={'Document type for ' + item.file.name}
              disabled={busy}
              value={item.type}
              onChange={(e) => {
                key.current = crypto.randomUUID()
                setFiles((current) =>
                  current.map((f, i) =>
                    i === index ? { ...f, type: e.target.value as UploadFile['type'] } : f,
                  ),
                )
              }}
            >
              <option value="BILL">Itemized bill</option>
              <option value="DISCHARGE_SUMMARY">Discharge summary</option>
              <option value="SUPPORTING_REPORT">Supporting report</option>
            </select>
            <button
              className="icon-button"
              disabled={busy}
              aria-label={'Remove ' + item.file.name}
              onClick={() => {
                key.current = crypto.randomUUID()
                setFiles((current) => current.filter((_, i) => i !== index))
              }}
            >
              <Trash2 size={16} />
            </button>
          </div>
        ))}
      </div>
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
      {progress && busy && (
        <div className="upload-progress" role="status">
          <span>{progress.step}</span>
          <progress
            max={progress.total}
            value={progress.completed}
            aria-label="Packet upload progress"
          />
        </div>
      )}
      <div className="dialog-actions">
        <button className="button secondary" onClick={onClose} disabled={busy}>
          Cancel
        </button>
        <button className="button primary" disabled={busy || !files.length} onClick={submit}>
          {busy ? <Loader2 size={17} className="spin" /> : <UploadCloud size={17} />}{' '}
          {busy ? 'Submitting packet…' : 'Start review'}
        </button>
      </div>
    </dialog>
  )
}

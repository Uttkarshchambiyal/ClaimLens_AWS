import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import './styles.css'
import {
  Activity as ActivityIcon,
  ArrowDownToLine,
  ArrowRight,
  BarChart3,
  Bot,
  Check,
  CheckCheck,
  ChevronDown,
  ChevronRight,
  CircleAlert,
  CircleCheck,
  Clock3,
  FileCheck2,
  FileSearch,
  FileText,
  FlaskConical,
  HelpCircle,
  Layers3,
  LayoutDashboard,
  Loader2,
  LockKeyhole,
  LogOut,
  Plus,
  Search,
  ShieldCheck,
  X,
} from 'lucide-react'
import {
  appMode,
  correctExtraction,
  createAnalysis,
  getAnalysis,
  getReport,
  listAnalyses,
  updateFinding,
} from './api'
import { requireUser, signOut } from './auth'
import { UploadDialog } from './components/UploadDialog'
import { SourceViewer } from './components/SourceViewer'
import { ClaimAnalytics, QueueAnalytics } from './components/ReviewAnalytics'
import { ThemeToggle } from './components/ui/theme-toggle'
import type {
  Analysis,
  CheckStatus,
  EvidenceRef,
  Finding,
  UploadFile,
  UploadProgress,
} from './types'

export const statusLabel: Record<CheckStatus, string> = {
  PASS: 'Passed',
  FINDING: 'Needs review',
  INSUFFICIENT_EVIDENCE: 'Evidence needed',
  NOT_APPLICABLE: 'Not applicable',
  ERROR: 'Check unavailable',
}
const documentLabel = {
  BILL: 'Itemized bill',
  DISCHARGE_SUMMARY: 'Discharge summary',
  SUPPORTING_REPORT: 'Supporting report',
}
const money = (value: number | null) =>
  value == null
    ? 'Not provided'
    : new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR',
        maximumFractionDigits: 2,
      }).format(value / 100)
const timestamp = (value: string) =>
  new Intl.DateTimeFormat('en-IN', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
const needsReview = (finding: Finding) =>
  ['FINDING', 'INSUFFICIENT_EVIDENCE', 'ERROR'].includes(finding.status)
const pending = (analysis: Analysis) => ['QUEUED', 'PROCESSING'].includes(analysis.status)
type WorkspaceView = 'dashboard' | 'workspace' | 'queue' | 'activity'
const viewFromUrl = (): WorkspaceView => {
  const value = new URLSearchParams(window.location.search).get('view')
  return value === 'dashboard' || value === 'queue' || value === 'activity' ? value : 'workspace'
}
function StatusIcon({ status, size = 16 }: { status: CheckStatus; size?: number }) {
  return status === 'PASS' ? (
    <CircleCheck size={size} />
  ) : status === 'INSUFFICIENT_EVIDENCE' ? (
    <HelpCircle size={size} />
  ) : status === 'NOT_APPLICABLE' ? (
    <Layers3 size={size} />
  ) : (
    <CircleAlert size={size} />
  )
}
function Badge({ status }: { status: CheckStatus }) {
  return (
    <span className={'badge status-' + status.toLowerCase()}>
      <StatusIcon status={status} />
      {statusLabel[status]}
    </span>
  )
}
function ProgressMetric({
  title,
  value,
  description,
}: {
  title: string
  value: number
  description: string
}) {
  return (
    <div className="metric-card">
      <div className="metric-label">
        {title}
        <span>{value}%</span>
      </div>
      <progress max={100} value={value} aria-label={title} />
      <small>{description}</small>
    </div>
  )
}
function Empty({
  title,
  detail,
  children,
}: {
  title: string
  detail: string
  children?: React.ReactNode
}) {
  return (
    <div className="empty-state">
      <FileSearch size={36} />
      <h3>{title}</h3>
      <p>{detail}</p>
      {children}
    </div>
  )
}
function HelpDialog({ close }: { close: () => void }) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    ref.current?.showModal()
  }, [])
  return (
    <dialog className="help-dialog" ref={ref} onCancel={close} aria-labelledby="review-guide-title">
      <div className="panel-header">
        <h2 id="review-guide-title">Review with confidence</h2>
        <button className="icon-button" onClick={close} aria-label="Close review guide">
          <X size={20} />
        </button>
      </div>
      <div className="help-content">
        <p>
          ClaimLens compares documents and presents discrepancies for a reviewer. It does not
          approve, reject, or pay claims.
        </p>
        <ol>
          <li>
            <strong>Inspect the finding.</strong> Review priority helps order your work. It is
            separate from extraction quality.
          </li>
          <li>
            <strong>Follow each citation.</strong> Open evidence to inspect the source, page, and
            confidence.
          </li>
          <li>
            <strong>Record your review.</strong> Acknowledge or resolve a finding. Missing reports
            require additional evidence.
          </li>
          <li>
            <strong>Export the record.</strong> The JSON report includes current dispositions and
            extraction corrections.
          </li>
        </ol>
        <div className="inline-note">
          Corrections preserve the original extraction. They are annotations and do not yet trigger
          a new analysis.
        </div>
        {appMode === 'mock' && (
          <p className="muted">
            The sample packets use fictional data. Demo changes are stored only for this browser
            tab’s session. No AWS services are invoked.
          </p>
        )}
      </div>
    </dialog>
  )
}

export function App() {
  const [analyses, setAnalyses] = useState<Analysis[]>([])
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [view, setView] = useState<WorkspaceView>(viewFromUrl)
  const [tab, setTab] = useState<'findings' | 'documents' | 'insights'>('findings')
  const [filter, setFilter] = useState('ALL')
  const [query, setQuery] = useState('')
  const [selectedId, setSelectedId] = useState('')
  const [evidenceId, setEvidenceId] = useState('')
  const [sourceOpen, setSourceOpen] = useState(() => window.innerWidth >= 1450)
  const [uploadOpen, setUploadOpen] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)
  const [token, setToken] = useState<string>()
  const [reviewer, setReviewer] = useState(appMode === 'mock' ? 'Demo reviewer' : 'Claims reviewer')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const sequence = useRef(0)

  const load = useCallback(async () => {
    const request = ++sequence.current
    setLoading(true)
    setError('')
    try {
      const user = await requireUser()
      if (appMode === 'production' && !user) return
      const jwt = user?.id_token
      setToken(jwt)
      if (user) setReviewer(String(user.profile.name || user.profile.email || 'Claims reviewer'))
      const records = await listAnalyses(jwt)
      const requested = new URLSearchParams(window.location.search).get('analysis')
      const initial = requested
        ? await getAnalysis(requested, jwt)
        : appMode === 'mock'
          ? records[0]
          : null
      if (request !== sequence.current) return
      setAnalyses(records)
      setAnalysis(initial || null)
      setView(initial ? viewFromUrl() : 'dashboard')
      setQuery('')
      setFilter('ALL')
      setSelectedId('')
      setEvidenceId('')
    } catch (e) {
      if (request === sequence.current)
        setError(e instanceof Error ? e.message : 'Unable to load your review workspace.')
    } finally {
      if (request === sequence.current) setLoading(false)
    }
  }, [])
  useEffect(() => {
    void load()
    const restore = () => {
      void load()
    }
    window.addEventListener('popstate', restore)
    return () => {
      window.removeEventListener('popstate', restore)
    }
  }, [load])
  useEffect(() => {
    if (!notice) return
    const timer = window.setTimeout(() => setNotice(''), 5000)
    return () => window.clearTimeout(timer)
  }, [notice])
  useEffect(() => {
    if (!analysis || !pending(analysis)) return
    let stopped = false
    const refresh = async () => {
      try {
        const result = await getAnalysis(analysis.id, token)
        if (!stopped) {
          setAnalysis(result)
          setAnalyses((current) => current.map((a) => (a.id === result.id ? result : a)))
        }
      } catch (e) {
        if (!stopped) setError(e instanceof Error ? e.message : 'Status could not be refreshed.')
      }
    }
    const timer = window.setInterval(refresh, 3000)
    return () => {
      stopped = true
      window.clearInterval(timer)
    }
  }, [analysis?.id, analysis?.status, token])

  const selectAnalysis = async (id: string) => {
    const request = ++sequence.current
    setBusy(true)
    setError('')
    try {
      const result = await getAnalysis(id, token)
      if (request !== sequence.current) return
      setAnalysis(result)
      setSelectedId('')
      setEvidenceId('')
      setFilter('ALL')
      setQuery('')
      setTab('findings')
      setView('workspace')
      window.history.pushState({}, '', '/review?analysis=' + encodeURIComponent(id))
    } catch (e) {
      if (request === sequence.current)
        setError(e instanceof Error ? e.message : 'Could not open analysis.')
    } finally {
      if (request === sequence.current) setBusy(false)
    }
  }
  const navigate = (next: WorkspaceView) => {
    setView(next)
    setQuery('')
    const params = new URLSearchParams()
    if (analysis) params.set('analysis', analysis.id)
    if (next !== 'workspace') params.set('view', next)
    const url = '/review' + (params.size ? '?' + params.toString() : '')
    if (window.location.pathname + window.location.search !== url)
      window.history.pushState({}, '', url)
  }
  const refreshRecord = async (id: string) => {
    const updated = await getAnalysis(id, token)
    setAnalysis((current) => (current?.id === id ? updated : current))
    setAnalyses((current) =>
      current.some((a) => a.id === id)
        ? current.map((a) => (a.id === id ? updated : a))
        : [updated, ...current],
    )
  }
  const visibleFindings = useMemo(
    () =>
      analysis?.findings.filter(
        (f) =>
          (filter === 'ALL' || (filter === 'ATTENTION' ? needsReview(f) : f.status === filter)) &&
          (f.title + ' ' + f.summary).toLowerCase().includes(query.toLowerCase()),
      ) || [],
    [analysis, filter, query],
  )
  const finding = visibleFindings.find((f) => f.id === selectedId) || visibleFindings[0]
  const evidence =
    finding?.evidence.find((e) => e.evidenceId === evidenceId) || finding?.evidence[0]
  const attention = analysis?.findings.filter(needsReview) || []
  const reviewed = attention.filter((f) => f.reviewerAction === 'RESOLVED').length
  const action = async (value: Finding['reviewerAction']) => {
    if (!analysis || !finding) return
    setBusy(true)
    setError('')
    try {
      await updateFinding(analysis.id, finding.id, value, token)
      await refreshRecord(analysis.id)
      setNotice('Review disposition saved.')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save disposition.')
    } finally {
      setBusy(false)
    }
  }
  const correct = async (value: string) => {
    if (!analysis || !evidence) return
    await correctExtraction(analysis.id, evidence.evidenceId, value, token)
    await refreshRecord(analysis.id)
    setNotice('Correction recorded. Original extraction and check results are preserved.')
  }
  const upload = async (
    files: UploadFile[],
    key: string,
    progress: (p: UploadProgress) => void,
  ) => {
    const result = await createAnalysis(files, token, key, progress)
    await refreshRecord(result.analysisId)
    await selectAnalysis(result.analysisId)
    setNotice(
      appMode === 'mock'
        ? 'Local packet created. Cloud extraction is unavailable in mock mode.'
        : 'Packet submitted. Processing will continue in the background.',
    )
  }
  const report = async () => {
    if (!analysis) return
    setBusy(true)
    setError('')
    try {
      const data = await getReport(analysis.id, token)
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }),
      )
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = analysis.claimId + '-review-v' + analysis.analysisVersion + '.json'
      anchor.click()
      const revoke = URL.revokeObjectURL.bind(URL)
      window.setTimeout(() => revoke(url), 1000)
      setNotice('Review report exported.')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Report could not be exported.')
    } finally {
      setBusy(false)
    }
  }

  const queue = analyses.filter((a) =>
    (a.claimId + ' ' + (a.scenario || '')).toLowerCase().includes(query.toLowerCase()),
  )
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to review content
      </a>
      <aside className="sidebar">
        <a className="brand" href="/" aria-label="ClaimLens home">
          <span className="brand-mark">
            <ShieldCheck size={23} />
          </span>
          <span>
            ClaimLens<small>CLAIM INTEGRITY</small>
          </span>
        </a>
        <div className="workspace-label">REVIEW WORKSPACE</div>
        <nav aria-label="Main navigation">
          <button
            aria-label="Dashboard"
            title="Dashboard"
            aria-current={view === 'dashboard' ? 'page' : undefined}
            className={'nav-item ' + (view === 'dashboard' ? 'active' : '')}
            onClick={() => navigate('dashboard')}
          >
            <LayoutDashboard size={19} />
            <span>Dashboard</span>
          </button>
          <button
            aria-label="Review queue"
            title="Review queue"
            aria-current={view === 'queue' ? 'page' : undefined}
            className={'nav-item ' + (view === 'queue' ? 'active' : '')}
            onClick={() => {
              navigate('queue')
            }}
          >
            <FileSearch size={19} />
            <span>Review queue</span>
            <b>{analyses.length}</b>
          </button>
          <button
            aria-label="Claim review"
            title="Claim review"
            aria-current={view === 'workspace' ? 'page' : undefined}
            className={'nav-item ' + (view === 'workspace' ? 'active' : '')}
            disabled={!analysis}
            onClick={() => navigate('workspace')}
          >
            <FileCheck2 size={19} />
            <span>Claim review</span>
          </button>
          <button
            aria-label="Review activity"
            title="Review activity"
            aria-current={view === 'activity' ? 'page' : undefined}
            className={'nav-item ' + (view === 'activity' ? 'active' : '')}
            onClick={() => navigate('activity')}
          >
            <ActivityIcon size={19} />
            <span>Review activity</span>
          </button>
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-note">
            <LockKeyhole size={18} />
            <strong>Evidence-led. Human-reviewed.</strong>
            <p>Every decision stays with you.</p>
          </div>
          <button
            className="nav-item"
            aria-label="Review guide"
            title="Review guide"
            onClick={() => setHelpOpen(true)}
          >
            <HelpCircle size={19} />
            <span>Review guide</span>
          </button>
          {appMode === 'production' && (
            <button
              className="nav-item"
              aria-label="Sign out"
              title="Sign out"
              onClick={() => signOut().catch((e) => setError(e.message))}
            >
              <LogOut size={19} />
              <span>Sign out</span>
            </button>
          )}
          <div className="profile">
            <span className="avatar">
              {appMode === 'mock' ? 'DR' : reviewer.slice(0, 2).toUpperCase()}
            </span>
            <div>
              <strong>{reviewer}</strong>
              <small>{appMode === 'mock' ? 'Demo workspace' : 'Claims reviewer'}</small>
            </div>
          </div>
        </div>
      </aside>
      <div className="app-content">
        <header className="topbar">
          <div className="breadcrumb">
            <span>Workspace</span>
            <ChevronRight size={14} />
            <strong>
              {view === 'dashboard'
                ? 'Dashboard'
                : view === 'queue'
                  ? 'Review queue'
                  : view === 'activity'
                    ? 'Activity'
                    : analysis?.claimId || 'Claim review'}
            </strong>
          </div>
          <div className="topbar-actions">
            <ThemeToggle />
            {appMode === 'production' && (
              <button
                className="icon-button mobile-signout"
                aria-label="Sign out on mobile"
                onClick={() => signOut().catch((e) => setError(e.message))}
              >
                <LogOut size={18} />
              </button>
            )}
            {appMode === 'mock' ? (
              <span className="mock-badge">
                <FlaskConical size={14} />
                Mock mode <span>· Synthetic data</span>
              </span>
            ) : (
              <span className="secure-badge">
                <LockKeyhole size={14} />
                Private workspace
              </span>
            )}
            <button
              className="icon-button"
              aria-label="Open review guide"
              onClick={() => setHelpOpen(true)}
            >
              <HelpCircle size={20} />
            </button>
          </div>
        </header>
        <main id="main-content" tabIndex={-1}>
          {error && (
            <div className="error-banner" role="alert">
              <CircleAlert size={19} />
              <span>{error}</span>
              <button className="text-button" onClick={() => void load()}>
                Retry
              </button>
              <button
                className="icon-button"
                aria-label="Dismiss error"
                onClick={() => setError('')}
              >
                <X size={17} />
              </button>
            </div>
          )}
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                {view === 'workspace' ? 'Claim integrity review' : 'Your workspace'}
              </div>
              <h1>
                {view === 'dashboard'
                  ? 'Review dashboard'
                  : view === 'queue'
                    ? 'Review queue'
                    : view === 'activity'
                      ? 'Review activity'
                      : analysis?.claimId || 'Claim review'}
                {view === 'workspace' && analysis && (
                  <span className={'priority priority-' + analysis.reviewPriority.toLowerCase()}>
                    {analysis.reviewPriority.toLowerCase()} priority
                  </span>
                )}
              </h1>
              <p>
                {view === 'dashboard'
                  ? 'Understand workload, extraction quality, and review progress at a glance.'
                  : view === 'queue'
                    ? 'A clear view of every packet that needs your attention.'
                    : view === 'activity'
                      ? 'Review dispositions and corrections for the selected claim.'
                      : 'Inspect discrepancies, follow the evidence, and record your review.'}
              </p>
            </div>
            <div className="heading-actions">
              <button
                className="button secondary"
                onClick={() => window.dispatchEvent(new Event('claimlens:open-assistant'))}
                aria-label="Open ClaimLens AI assistant"
              >
                <Bot size={17} />
                Ask ClaimLens
              </button>
              {view === 'workspace' && (
                <button
                  className="button secondary"
                  disabled={!analysis || busy || pending(analysis)}
                  onClick={report}
                >
                  <ArrowDownToLine size={17} />
                  Export report
                </button>
              )}
              <button
                className="button primary"
                disabled={loading}
                onClick={() => setUploadOpen(true)}
              >
                <Plus size={18} />
                New packet
              </button>
            </div>
          </div>
          {loading ? (
            <div className="loading-state" role="status">
              <Loader2 className="spin" size={28} />
              <h3>Opening your workspace</h3>
              <p>Loading claims and review records…</p>
            </div>
          ) : view === 'dashboard' ? (
            <>
              <div className="queue-metrics dashboard-metrics">
                <div>
                  <span>Total packets</span>
                  <strong>{analyses.length.toString().padStart(2, '0')}</strong>
                  <small>Visible in your private workspace</small>
                </div>
                <div>
                  <span>Ready for review</span>
                  <strong>
                    {analyses
                      .filter((item) =>
                        ['COMPLETED', 'COMPLETED_WITH_WARNINGS'].includes(item.status),
                      )
                      .length.toString()
                      .padStart(2, '0')}
                  </strong>
                  <small>Extraction and checks completed</small>
                </div>
                <div>
                  <span>Processing now</span>
                  <strong>{analyses.filter(pending).length.toString().padStart(2, '0')}</strong>
                  <small>Updates automatically in the background</small>
                </div>
                <div>
                  <span>Average quality</span>
                  <strong>
                    {analyses.length
                      ? Math.round(
                          analyses.reduce((total, item) => total + item.extractionQuality, 0) /
                            analyses.length,
                        )
                      : 0}
                    <small>%</small>
                  </strong>
                  <small>Across all extracted packets</small>
                </div>
              </div>
              <QueueAnalytics analyses={analyses} />
              <section className="dashboard-flow" aria-labelledby="review-path-title">
                <div className="analytics-heading">
                  <div>
                    <span className="eyebrow">How your data moves</span>
                    <h2 id="review-path-title">One transparent review path</h2>
                    <p>Every stage stays visible, from upload through the human decision.</p>
                  </div>
                </div>
                <div className="dashboard-flow-grid">
                  <div>
                    <FileText size={20} />
                    <span>01</span>
                    <strong>Upload</strong>
                    <small>Secure packet intake</small>
                  </div>
                  <div>
                    <FileSearch size={20} />
                    <span>02</span>
                    <strong>Extract</strong>
                    <small>Textract reads source fields</small>
                  </div>
                  <div>
                    <ShieldCheck size={20} />
                    <span>03</span>
                    <strong>Verify</strong>
                    <small>Rules find review signals</small>
                  </div>
                  <div>
                    <CheckCheck size={20} />
                    <span>04</span>
                    <strong>Decide</strong>
                    <small>A reviewer records the outcome</small>
                  </div>
                </div>
              </section>
              <section className="dashboard-recent" aria-labelledby="recent-packets-title">
                <div className="panel-header">
                  <div>
                    <span className="eyebrow">Recent work</span>
                    <h2 id="recent-packets-title">Latest claim packets</h2>
                  </div>
                  <button className="text-button" onClick={() => navigate('queue')}>
                    View full queue <ArrowRight size={16} />
                  </button>
                </div>
                <div className="dashboard-recent-grid">
                  {analyses.slice(0, 3).map((item) => (
                    <button key={item.id} onClick={() => void selectAnalysis(item.id)}>
                      <span className={'priority priority-' + item.reviewPriority.toLowerCase()}>
                        {item.reviewPriority.toLowerCase()}
                      </span>
                      <strong>{item.claimId}</strong>
                      <small>
                        {item.findings.filter(needsReview).length} findings ·{' '}
                        {item.documents.length} documents
                      </small>
                      <span className="recent-coverage">
                        <i style={{ width: `${item.coverage}%` }} />
                        {item.coverage}% coverage
                      </span>
                    </button>
                  ))}
                  {!analyses.length && (
                    <Empty
                      title="No packets yet"
                      detail="Upload your first packet to populate this dashboard."
                    />
                  )}
                </div>
              </section>
            </>
          ) : view === 'queue' ? (
            <>
              <div className="queue-metrics">
                <div>
                  <span>Packets in workspace</span>
                  <strong>{analyses.length.toString().padStart(2, '0')}</strong>
                  <small>
                    {appMode === 'mock'
                      ? 'Synthetic demonstration packets'
                      : 'Tenant-authorized analyses'}
                  </small>
                </div>
                <div>
                  <span>High review priority</span>
                  <strong>
                    {analyses
                      .filter((a) => a.reviewPriority === 'HIGH')
                      .length.toString()
                      .padStart(2, '0')}
                  </strong>
                  <small>Discrepancies to inspect first</small>
                </div>
                <div>
                  <span>Evidence incomplete</span>
                  <strong>
                    {analyses
                      .filter((a) => a.coverage < 100)
                      .length.toString()
                      .padStart(2, '0')}
                  </strong>
                  <small>Additional review may be required</small>
                </div>
              </div>
              <section className="queue-panel">
                <div className="queue-toolbar">
                  <h2>
                    {appMode === 'mock' ? 'Sample packets' : 'Claim packets'}{' '}
                    <span>{analyses.length}</span>
                  </h2>
                  <label className="search-field">
                    <Search size={17} />
                    <input
                      aria-label="Search packets"
                      placeholder="Search claims or scenarios…"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                    />
                  </label>
                </div>
                <div className="table-scroll">
                  <table className="queue-table">
                    <thead>
                      <tr>
                        <th>Claim packet</th>
                        <th>Review priority</th>
                        <th>Findings</th>
                        <th>Coverage</th>
                        <th>Documents</th>
                        <th>
                          <span className="sr-only">Open</span>
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {queue.map((item) => (
                        <tr key={item.id}>
                          <td>
                            <button
                              className="claim-link"
                              onClick={() => void selectAnalysis(item.id)}
                            >
                              {item.claimId}
                              <ArrowRight size={15} />
                            </button>
                            <small>{item.scenario || timestamp(item.createdAt)}</small>
                          </td>
                          <td>
                            <span
                              className={'priority priority-' + item.reviewPriority.toLowerCase()}
                            >
                              {item.reviewPriority.toLowerCase()}
                            </span>
                          </td>
                          <td>{item.findings.filter(needsReview).length} to review</td>
                          <td>
                            <div className="table-coverage">
                              <progress
                                max={100}
                                value={item.coverage}
                                aria-label={'Check coverage for ' + item.claimId}
                              />
                              <span>{item.coverage}%</span>
                            </div>
                          </td>
                          <td>
                            <span className="document-count">
                              <FileText size={15} />
                              {item.documents.length} files
                            </span>
                          </td>
                          <td>
                            <button
                              className="icon-button"
                              aria-label={'Open ' + item.claimId}
                              onClick={() => void selectAnalysis(item.id)}
                            >
                              <ChevronRight size={18} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {!queue.length && (
                  <Empty
                    title="No packets found"
                    detail={
                      analyses.length
                        ? 'Try a different search.'
                        : 'Upload a claim packet to begin your first review.'
                    }
                  />
                )}
              </section>
              {appMode === 'mock' && (
                <div className="demo-note">
                  <FlaskConical size={19} />
                  <div>
                    <strong>Explore four review scenarios</strong>
                    <p>
                      Consistent, inconsistent, ambiguous, and legitimate edge-case packets. Review
                      actions persist in this tab; no cloud services are used.
                    </p>
                  </div>
                </div>
              )}
            </>
          ) : !analysis ? (
            <Empty
              title="Your workspace is ready"
              detail="Choose a claim from the queue or upload a new packet."
            >
              <button className="button primary" onClick={() => navigate('queue')}>
                Open review queue
                <ArrowRight size={16} />
              </button>
            </Empty>
          ) : view === 'activity' ? (
            <section className="activity-panel">
              <div className="panel-header">
                <h2>{analysis.claimId}</h2>
                <button className="text-button" onClick={() => navigate('workspace')}>
                  Return to review
                  <ArrowRight size={16} />
                </button>
              </div>
              <div className="activity-list">
                <div className="activity-item">
                  <span className="activity-icon">
                    <FileText size={17} />
                  </span>
                  <div>
                    <strong>Analysis created</strong>
                    <p>
                      {analysis.documents.length} documents · Analysis v{analysis.analysisVersion}
                    </p>
                    <small>{timestamp(analysis.createdAt)}</small>
                  </div>
                </div>
                {(analysis.activity || []).map((event) => (
                  <div className="activity-item" key={event.id}>
                    <span className="activity-icon">
                      <CheckCheck size={17} />
                    </span>
                    <div>
                      <strong>{event.title}</strong>
                      <p>{event.detail}</p>
                      <small>
                        {timestamp(event.at)}
                        {event.actorId ? ' · Reviewer ' + event.actorId : ''}
                      </small>
                    </div>
                  </div>
                ))}
                {!analysis.activity?.length && (
                  <p className="muted">
                    No reviewer actions yet. Recorded actions will appear here.
                  </p>
                )}
              </div>
            </section>
          ) : (
            <>
              <div className="claim-context">
                <div>
                  <span className="context-icon">
                    <FileText size={19} />
                  </span>
                  <strong>{analysis.scenario || 'Claim packet'}</strong>
                  <span className="context-divider" />
                  <span>
                    Claimed amount <b>{money(analysis.claimedAmountPaise)}</b>
                  </span>
                  <span className="context-divider" />
                  <span>{analysis.documents.length} documents</span>
                </div>
                {appMode === 'mock' && (
                  <label className="scenario-switch">
                    <span className="sr-only">Switch sample packet</span>
                    <FlaskConical size={15} />
                    <select
                      value={analysis.id}
                      onChange={(e) => void selectAnalysis(e.target.value)}
                      aria-label="Switch sample packet"
                    >
                      {analyses.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.scenario || a.claimId}
                        </option>
                      ))}
                    </select>
                    <ChevronDown size={14} />
                  </label>
                )}
              </div>
              <div className="metrics-grid">
                <div className="metric-card attention-metric">
                  <span className="metric-symbol">
                    <CircleAlert size={21} />
                  </span>
                  <div>
                    <span className="metric-label">Needs attention</span>
                    <strong>
                      {attention.length}
                      <small>checks</small>
                    </strong>
                  </div>
                  <span className="metric-caption">{reviewed} resolved</span>
                </div>
                <ProgressMetric
                  title="Extraction quality"
                  value={analysis.extractionQuality}
                  description="Confidence in extracted fields"
                />
                <ProgressMetric
                  title="Check coverage"
                  value={analysis.coverage}
                  description="Checks with sufficient evidence"
                />
                <div className="metric-card review-metric">
                  <div className="metric-label">
                    Analysis status
                    <Clock3 size={16} />
                  </div>
                  <strong>
                    {pending(analysis)
                      ? 'Processing'
                      : analysis.status === 'FAILED'
                        ? 'Failed'
                        : 'Ready to review'}
                  </strong>
                  <small>
                    Version {analysis.analysisVersion} ·{' '}
                    {analysis.status === 'COMPLETED_WITH_WARNINGS'
                      ? 'Coverage gaps present'
                      : pending(analysis)
                        ? 'Updates automatically'
                        : 'Human review required'}
                  </small>
                </div>
              </div>
              <div className="workspace-tabs">
                <div
                  role="tablist"
                  aria-label="Review sections"
                  onKeyDown={(event) => {
                    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
                    event.preventDefault()
                    const tabs = ['findings', 'documents', 'insights'] as const
                    const current = tabs.indexOf(tab)
                    const next =
                      event.key === 'Home'
                        ? tabs[0]
                        : event.key === 'End'
                          ? tabs[tabs.length - 1]
                          : tabs[
                              (current + (event.key === 'ArrowRight' ? 1 : tabs.length - 1)) %
                                tabs.length
                            ]
                    setTab(next)
                    document.getElementById('review-' + next + '-tab')?.focus()
                  }}
                >
                  <button
                    role="tab"
                    id="review-findings-tab"
                    aria-controls="review-findings-panel"
                    tabIndex={tab === 'findings' ? 0 : -1}
                    aria-selected={tab === 'findings'}
                    className={tab === 'findings' ? 'active' : ''}
                    onClick={() => setTab('findings')}
                  >
                    <FileCheck2 size={17} />
                    Findings<span>{analysis.findings.length}</span>
                  </button>
                  <button
                    role="tab"
                    id="review-documents-tab"
                    aria-controls="review-documents-panel"
                    tabIndex={tab === 'documents' ? 0 : -1}
                    aria-selected={tab === 'documents'}
                    className={tab === 'documents' ? 'active' : ''}
                    onClick={() => setTab('documents')}
                  >
                    <Layers3 size={17} />
                    Documents<span>{analysis.documents.length}</span>
                  </button>
                  <button
                    role="tab"
                    id="review-insights-tab"
                    aria-controls="review-insights-panel"
                    tabIndex={tab === 'insights' ? 0 : -1}
                    aria-selected={tab === 'insights'}
                    className={tab === 'insights' ? 'active' : ''}
                    onClick={() => setTab('insights')}
                  >
                    <BarChart3 size={17} />
                    Insights
                  </button>
                </div>
                <span className="review-hint">
                  <ShieldCheck size={15} />
                  For human review
                </span>
              </div>
              <div
                role="tabpanel"
                id={'review-' + tab + '-panel'}
                aria-labelledby={'review-' + tab + '-tab'}
              >
                {pending(analysis) ? (
                  <div className="processing-panel" role="status">
                    <Loader2 className="spin" size={28} />
                    <h3>
                      {analysis.status === 'QUEUED'
                        ? 'Your packet is queued'
                        : 'Reading your documents'}
                    </h3>
                    <p>Extraction and checks run in the background. You can return to the queue.</p>
                    <button className="button secondary" onClick={() => navigate('queue')}>
                      Back to queue
                    </button>
                  </div>
                ) : analysis.status === 'FAILED' ? (
                  <div className="processing-panel processing-failed" role="alert">
                    <CircleAlert size={30} />
                    <span className="eyebrow">Processing stopped safely</span>
                    <h3>This packet could not be analyzed</h3>
                    <p>
                      The documents were uploaded, but a cloud extraction step failed. ClaimLens did
                      not create findings from incomplete evidence.
                    </p>
                    <div className="failure-actions">
                      <button className="button secondary" onClick={() => navigate('queue')}>
                        Back to queue
                      </button>
                      <button className="button primary" onClick={() => setUploadOpen(true)}>
                        <Plus size={17} /> Try a new packet
                      </button>
                    </div>
                  </div>
                ) : tab === 'insights' ? (
                  <ClaimAnalytics analysis={analysis} />
                ) : tab === 'documents' ? (
                  <section className="documents-panel">
                    {analysis.documents.map((doc) => (
                      <div className="document-row" key={doc.id}>
                        <span className="document-type-icon">
                          <FileText size={23} />
                        </span>
                        <div>
                          <strong>{doc.name}</strong>
                          <small>
                            {documentLabel[doc.type]} · Version {doc.version} ·{' '}
                            {doc.pages || 'Unknown'} pages
                          </small>
                        </div>
                        <span className={'document-state ' + doc.status.toLowerCase()}>
                          {doc.status === 'READY' ? <Check size={15} /> : <CircleAlert size={15} />}{' '}
                          {doc.status.toLowerCase().replaceAll('_', ' ')}
                        </span>
                        <span className="muted">
                          {doc.extractionQuality == null
                            ? 'Quality unavailable'
                            : doc.extractionQuality + '% quality'}
                        </span>
                        <button
                          className="button secondary small"
                          disabled={
                            !analysis.findings.some((f) =>
                              f.evidence.some((e) => e.documentId === doc.id),
                            )
                          }
                          onClick={() => {
                            const match = analysis.findings.find((f) =>
                              f.evidence.some((e) => e.documentId === doc.id),
                            )
                            if (match) {
                              setFilter('ALL')
                              setQuery('')
                              setSelectedId(match.id)
                              setEvidenceId(
                                match.evidence.find((e) => e.documentId === doc.id)!.evidenceId,
                              )
                              setTab('findings')
                              setSourceOpen(true)
                            }
                          }}
                        >
                          View evidence
                          <ArrowRight size={15} />
                        </button>
                      </div>
                    ))}
                  </section>
                ) : (
                  <div className={'review-body ' + (sourceOpen ? 'with-source' : '')}>
                    <section className="findings-workspace">
                      <div className="findings-toolbar">
                        <div className="filter-pills" aria-label="Filter checks">
                          {[
                            ['ALL', 'All checks'],
                            ['ATTENTION', 'Needs attention'],
                            ['PASS', 'Passed'],
                          ].map(([value, label]) => (
                            <button
                              key={value}
                              aria-pressed={filter === value}
                              className={filter === value ? 'active' : ''}
                              onClick={() => {
                                setFilter(value)
                                setSelectedId('')
                                setEvidenceId('')
                              }}
                            >
                              {label}
                            </button>
                          ))}
                        </div>
                        <label className="search-field compact-search">
                          <Search size={16} />
                          <input
                            aria-label="Search findings"
                            placeholder="Search checks…"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                          />
                        </label>
                      </div>
                      <div className="review-columns">
                        <div className="finding-list" aria-label="Checks">
                          {visibleFindings.map((item, index) => (
                            <button
                              aria-pressed={finding?.id === item.id}
                              className={
                                'finding-row ' + (finding?.id === item.id ? 'selected' : '')
                              }
                              key={item.id}
                              onClick={() => {
                                setSelectedId(item.id)
                                setEvidenceId('')
                              }}
                            >
                              <div className="finding-row-top">
                                <span
                                  className={'finding-symbol status-' + item.status.toLowerCase()}
                                >
                                  <StatusIcon status={item.status} />
                                </span>
                                <span className="check-number">
                                  CHECK {String(index + 1).padStart(2, '0')}
                                </span>
                                {item.reviewerAction === 'RESOLVED' && (
                                  <CheckCheck size={16} className="resolved-icon" />
                                )}
                              </div>
                              <strong>{item.title}</strong>
                              <span className="finding-row-bottom">
                                <span>{statusLabel[item.status]}</span>
                                <ChevronRight size={15} />
                              </span>
                            </button>
                          ))}
                          {!visibleFindings.length && (
                            <Empty
                              title="No matching checks"
                              detail="Try another filter or search."
                            />
                          )}
                        </div>
                        {finding ? (
                          <article className="finding-detail" key={finding.id}>
                            <div className="detail-heading">
                              <Badge status={finding.status} />
                              <span className="check-category">
                                {finding.checkId.split('.')[0]} check
                              </span>
                            </div>
                            <h2>{finding.title}</h2>
                            <p className="finding-summary">{finding.summary}</p>
                            {finding.requestedEvidence && (
                              <div className="evidence-request">
                                <HelpCircle size={20} />
                                <div>
                                  <strong>Request additional evidence</strong>
                                  <p>{finding.requestedEvidence}</p>
                                </div>
                              </div>
                            )}
                            <div className="evidence-heading">
                              <h3>
                                Source evidence <span>{finding.evidence.length}</span>
                              </h3>
                              <span>Traceable to the document</span>
                            </div>
                            <div className="evidence-list">
                              {finding.evidence.map((ref, i) => (
                                <button
                                  aria-label={
                                    'View source ' +
                                    String.fromCharCode(65 + i) +
                                    ', ' +
                                    ref.documentName +
                                    ', page ' +
                                    ref.page
                                  }
                                  className={
                                    'evidence-card ' +
                                    (sourceOpen && evidence?.evidenceId === ref.evidenceId
                                      ? 'selected'
                                      : '')
                                  }
                                  key={ref.evidenceId}
                                  onClick={() => {
                                    setEvidenceId(ref.evidenceId)
                                    setSourceOpen(true)
                                  }}
                                >
                                  <div className="evidence-card-top">
                                    <span className="evidence-letter">
                                      {String.fromCharCode(65 + i)}
                                    </span>
                                    <span className="evidence-name">{ref.documentName}</span>
                                    <span className="page-badge">p. {ref.page}</span>
                                  </div>
                                  <blockquote>{ref.excerpt}</blockquote>
                                  <div className="evidence-card-footer">
                                    <span>
                                      <span className="confidence-dot" />
                                      {ref.confidence.toFixed(1)}% confidence
                                    </span>
                                    <span>
                                      View source
                                      <ArrowRight size={14} />
                                    </span>
                                  </div>
                                </button>
                              ))}
                            </div>
                            {!finding.evidence.length && (
                              <div className="missing-evidence">
                                <FileSearch size={22} />
                                <p>
                                  No reliable source was extracted for this check. The result is not
                                  a clean pass.
                                </p>
                              </div>
                            )}
                            <div className="disposition">
                              <div>
                                <h3>Reviewer disposition</h3>
                                <p>Record how you handled this finding.</p>
                              </div>
                              <div className="disposition-options">
                                {(['OPEN', 'ACKNOWLEDGED', 'RESOLVED'] as const).map((value) => (
                                  <button
                                    disabled={busy}
                                    aria-pressed={(finding.reviewerAction || 'OPEN') === value}
                                    className={
                                      (finding.reviewerAction || 'OPEN') === value ? 'active' : ''
                                    }
                                    key={value}
                                    onClick={() => void action(value)}
                                  >
                                    {value === 'RESOLVED' ? (
                                      <CheckCheck size={15} />
                                    ) : value === 'ACKNOWLEDGED' ? (
                                      <Check size={15} />
                                    ) : (
                                      <Clock3 size={15} />
                                    )}{' '}
                                    {value === 'OPEN'
                                      ? 'Open'
                                      : value === 'ACKNOWLEDGED'
                                        ? 'Acknowledged'
                                        : 'Resolved'}
                                  </button>
                                ))}
                              </div>
                              <small>
                                <ShieldCheck size={13} />
                                Dispositions do not approve, reject, or pay a claim.
                              </small>
                            </div>
                          </article>
                        ) : (
                          <Empty
                            title="Nothing to display"
                            detail="Choose a different filter to see the other checks."
                          />
                        )}
                      </div>
                    </section>
                    {sourceOpen && (
                      <>
                        <button
                          className="viewer-backdrop"
                          aria-label="Close source panel"
                          onClick={() => setSourceOpen(false)}
                        />
                        <SourceViewer
                          analysis={analysis}
                          evidence={evidence as EvidenceRef | undefined}
                          token={token}
                          onClose={() => setSourceOpen(false)}
                          onCorrect={correct}
                        />
                      </>
                    )}
                  </div>
                )}
              </div>
              <footer className="workspace-footer">
                <span>
                  <LockKeyhole size={13} />
                  {appMode === 'mock'
                    ? 'Synthetic data · stored in this tab only'
                    : 'Tenant-authorized document access'}
                </span>
                <span>ClaimLens · Evidence for every review</span>
              </footer>
            </>
          )}
        </main>
      </div>
      {uploadOpen && <UploadDialog onClose={() => setUploadOpen(false)} onStart={upload} />}
      {helpOpen && <HelpDialog close={() => setHelpOpen(false)} />}
      {notice && (
        <div className="toast" role="status">
          <CircleCheck size={19} />
          <span>{notice}</span>
          <button aria-label="Dismiss notification" onClick={() => setNotice('')}>
            <X size={15} />
          </button>
        </div>
      )}
    </div>
  )
}

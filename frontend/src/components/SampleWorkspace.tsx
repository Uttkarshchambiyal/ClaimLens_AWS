import { useState } from 'react'
import {
  ArrowRight,
  CheckCircle2,
  FileText,
  FlaskConical,
  ScanText,
  ShieldCheck,
} from 'lucide-react'

const documents = [
  { title: 'CityCare itemized bill', type: 'Itemized bill', icon: FileText },
  { title: 'CityCare discharge summary', type: 'Discharge summary', icon: FileText },
  { title: 'CityCare operative report', type: 'Supporting report', icon: FileText },
]

export function SampleWorkspace() {
  const [starting, setStarting] = useState(false)
  const start = () => {
    setStarting(true)
    window.setTimeout(() => window.location.assign('/review?sample=1&analysis=anl_demo_7J3K'), 650)
  }

  return (
    <main className="sample-workspace" aria-labelledby="sample-workspace-title">
      <a className="sample-workspace-brand" href="/">
        <span>
          <ShieldCheck size={19} />
        </span>{' '}
        ClaimLens
      </a>
      <section className="sample-workspace-card">
        <div className="sample-workspace-kicker">
          <FlaskConical size={15} /> Guided sample workspace
        </div>
        <h1 id="sample-workspace-title">See the complete review in one click.</h1>
        <p>
          This fictional CityCare packet is already prepared. No account, upload, or AWS service is
          required to explore the evidence, findings, and reviewer actions.
        </p>
        <div className="sample-workspace-files" aria-label="Preloaded sample documents">
          {documents.map(({ title, type, icon: Icon }) => (
            <article key={title}>
              <span>
                <Icon size={18} />
              </span>
              <div>
                <strong>{title}</strong>
                <small>{type} - preloaded synthetic evidence</small>
              </div>
              <CheckCircle2 size={18} />
            </article>
          ))}
        </div>
        <div className="sample-workspace-result">
          <ScanText size={20} />
          <div>
            <strong>What you will see</strong>
            <span>
              Source-linked findings, review priority, confidence, evidence pages, and a
              human-review trail.
            </span>
          </div>
        </div>
        <button className="sample-workspace-start" onClick={start} disabled={starting}>
          {starting ? 'Opening completed review…' : 'Run sample review'} <ArrowRight size={18} />
        </button>
        <small>Fictional demonstration only. It never approves, rejects, or pays a claim.</small>
      </section>
    </main>
  )
}

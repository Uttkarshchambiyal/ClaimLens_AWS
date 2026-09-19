import { useEffect, useRef, useState } from 'react'
import {
  ArrowUpRight,
  Check,
  Cpu,
  Database,
  FileText,
  Layers3,
  LockKeyhole,
  Pause,
  Play,
  ScanText,
  ShieldCheck,
  Sparkles,
  Workflow,
  X,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { ThemeToggle } from '@/components/ui/theme-toggle'

const SERVICES = [
  { name: 'Amazon S3', icon: Layers3 },
  { name: 'Textract', icon: ScanText },
  { name: 'Bedrock', icon: Sparkles },
  { name: 'Lambda', icon: Cpu },
  { name: 'DynamoDB', icon: Database },
  { name: 'Cognito', icon: LockKeyhole },
]

export interface HeroSectionProps {
  reviewHref?: string
  className?: string
}

function ArrowAction({ children }: { children: React.ReactNode }) {
  return (
    <span className="aero-action">
      <span>{children}</span>
      <span className="aero-action-icon" aria-hidden="true">
        <ArrowUpRight size={19} />
      </span>
    </span>
  )
}

function SamplePreview({ reviewHref, close }: { reviewHref: string; close: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    dialog.current?.showModal()
  }, [])
  return (
    <dialog ref={dialog} onCancel={close} className="aero-dialog" aria-labelledby="sample-title">
      <div className="aero-dialog-topline">
        <span>
          <Sparkles size={14} /> Synthetic demonstration
        </span>
        <button onClick={close} className="aero-icon-button" aria-label="Close sample preview">
          <X size={20} />
        </button>
      </div>
      <h2 id="sample-title">From discrepancy to the exact source.</h2>
      <p>
        A fictional hospital bill shows a total that differs from its line items. ClaimLens brings
        both values into one clear review.
      </p>
      <div className="aero-sample-card">
        <div className="aero-sample-file">
          <FileText size={16} /> CityCare_itemized_bill.pdf · Page 3
        </div>
        <div>
          <span>Stated invoice total</span>
          <strong>₹248,500.00</strong>
        </div>
        <div>
          <span>Extracted line items</span>
          <strong>₹241,500.00</strong>
        </div>
        <div className="aero-sample-difference">
          <span>Difference to review</span>
          <strong>₹7,000.00</strong>
        </div>
      </div>
      <p className="aero-boundary">
        <ShieldCheck size={16} /> This finding asks for human review. It does not decide whether a
        claim should be paid.
      </p>
      <a href={reviewHref} className="aero-dialog-cta">
        <ArrowAction>Open review workspace</ArrowAction>
      </a>
    </dialog>
  )
}

export default function HeroSection({ reviewHref = '/review', className }: HeroSectionProps) {
  const [previewOpen, setPreviewOpen] = useState(false)
  const [paused, setPaused] = useState(false)
  return (
    <div className={cn('aero-hero', className)}>
      <header className="aero-header">
        <a href="/" className="aero-brand" aria-label="ClaimLens home">
          <span>
            <ShieldCheck size={19} />
          </span>
          ClaimLens
        </a>
        <nav aria-label="Site navigation">
          <button onClick={() => setPreviewOpen(true)}>How it works</button>
          <a href={reviewHref}>Open workspace</a>
          <ThemeToggle className="aero-theme-toggle" />
        </nav>
      </header>

      <main className="aero-grid">
        <section className="aero-image-panel" aria-label="Clinician reviewing digital documents">
          <img
            src="/claimlens-review.jpg"
            alt="Clinician reviewing healthcare information on a mobile device"
          />
          <div className="aero-image-shade" />
          <div className="aero-image-note">
            <span className="aero-note-icon">
              <Workflow size={20} />
            </span>
            <span>
              <small>Every finding stays traceable</small>
              <strong>Source-linked. Human-reviewed.</strong>
            </span>
          </div>
        </section>

        <section className="aero-copy-panel">
          <div className="aero-copy">
            <span className="aero-kicker">
              <Sparkles size={14} /> Clarity in every claim
            </span>
            <h1>
              Every claim.
              <br />
              Clear evidence.
              <br />
              <em>Confident review.</em>
            </h1>
            <p>
              Turn complex medical documents into a calm, traceable review. Find discrepancies, open
              the exact source, and keep every decision in human hands.
            </p>
            <div className="aero-actions">
              <a href={reviewHref} className="aero-primary-link">
                <ArrowAction>Start reviewing</ArrowAction>
              </a>
              <button className="aero-secondary-link" onClick={() => setPreviewOpen(true)}>
                <Play size={15} /> Explore a sample
              </button>
            </div>
            <div className="aero-trust-row">
              <div className="aero-avatars" aria-hidden="true">
                <span>CL</span>
                <span>TX</span>
                <span>BR</span>
              </div>
              <div>
                <strong>One review path</strong>
                <span>Upload · extract · verify · decide</span>
              </div>
            </div>
            <div className="aero-promises">
              <span>
                <Check size={14} /> Source-linked findings
              </span>
              <span>
                <Check size={14} /> Human-led decisions
              </span>
            </div>
            <div className="aero-quality">
              <span>Synthetic data</span>
              <div
                role="meter"
                aria-label="Sample extraction quality"
                aria-valuenow={94}
                aria-valuemin={0}
                aria-valuemax={100}
              >
                <i />
              </div>
              <strong>94% sample extraction quality</strong>
            </div>
          </div>

          <section
            className={cn('aero-services', paused && 'hero-services-paused')}
            aria-label="AWS architecture services"
          >
            <div className="aero-services-heading">
              <span>Built on the AWS review stack</span>
              <button
                onClick={() => setPaused((value) => !value)}
                aria-label={paused ? 'Play service animation' : 'Pause service animation'}
              >
                {paused ? <Play size={13} /> : <Pause size={13} />}
              </button>
            </div>
            <div className="aero-marquee-mask">
              <div className="hero-marquee aero-marquee">
                {[0, 1].map((copy) => (
                  <div key={copy} aria-hidden={copy === 1}>
                    {SERVICES.map((service) => (
                      <span key={service.name}>
                        <service.icon size={18} strokeWidth={1.6} />
                        {service.name}
                      </span>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          </section>
        </section>
      </main>
      {previewOpen && <SamplePreview reviewHref={reviewHref} close={() => setPreviewOpen(false)} />}
    </div>
  )
}

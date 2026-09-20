import { useEffect, useRef, useState } from 'react'
import {
  ArrowUpRight,
  Check,
  ClipboardCheck,
  Cpu,
  Database,
  FileUp,
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
import { appMode } from '@/appConfig'
import { getOptionalUser, type ClaimLensUser } from '@/auth'
import { CinematicReviewFooter } from './cinematic-review-footer'

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
  loginHref?: string
  signupHref?: string
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

function firstName(user: ClaimLensUser) {
  const value = String(user.profile.name || user.profile.email || 'Reviewer')
  const first = value.split(/[@\s]/)[0].replace(/[._-]+/g, ' ')
  return first.charAt(0).toUpperCase() + first.slice(1)
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

export default function HeroSection({
  reviewHref = '/review',
  loginHref = '/auth/login',
  signupHref = '/auth/signup',
  className,
}: HeroSectionProps) {
  const [previewOpen, setPreviewOpen] = useState(false)
  const [paused, setPaused] = useState(false)
  const [session, setSession] = useState<'loading' | 'guest' | 'signed-in'>(
    appMode === 'mock' ? 'guest' : 'loading',
  )
  const [viewerName, setViewerName] = useState('Reviewer')
  useEffect(() => {
    let active = true
    const refreshSession = () => {
      void getOptionalUser().then((user) => {
        if (!active) return
        if (user) {
          setViewerName(firstName(user))
          setSession('signed-in')
        } else {
          setSession('guest')
        }
      })
    }
    const refreshVisibleSession = () => {
      if (document.visibilityState === 'visible') refreshSession()
    }
    refreshSession()
    window.addEventListener('pageshow', refreshSession)
    window.addEventListener('focus', refreshSession)
    window.addEventListener('claimlens:auth-changed', refreshSession)
    document.addEventListener('visibilitychange', refreshVisibleSession)
    return () => {
      active = false
      window.removeEventListener('pageshow', refreshSession)
      window.removeEventListener('focus', refreshSession)
      window.removeEventListener('claimlens:auth-changed', refreshSession)
      document.removeEventListener('visibilitychange', refreshVisibleSession)
    }
  }, [])
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
          <a className="aero-how-link" href="#how-it-works">
            How it works
          </a>
          {session === 'loading' ? (
            <span className="aero-session-loading" aria-label="Checking account session" />
          ) : session === 'signed-in' ? (
            <a className="aero-welcome-link" href={reviewHref}>
              Welcome, {viewerName}
            </a>
          ) : (
            <>
              <a className="aero-login-link" href={loginHref}>
                Log in
              </a>
              <a className="aero-signup-link" href={signupHref}>
                Create account
              </a>
            </>
          )}
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
              {session === 'signed-in' ? (
                <a href={reviewHref} className="aero-primary-link">
                  <ArrowAction>Open your workspace</ArrowAction>
                </a>
              ) : session === 'guest' ? (
                <>
                  <a href={signupHref} className="aero-primary-link">
                    <ArrowAction>Create your account</ArrowAction>
                  </a>
                  <a href={loginHref} className="aero-login-action">
                    <LockKeyhole size={15} /> Log in
                  </a>
                </>
              ) : (
                <span className="aero-action-loading" aria-label="Checking account session" />
              )}
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

      <section className="aero-path" id="how-it-works" aria-labelledby="review-path-title">
        <div className="aero-path-heading">
          <span className="aero-kicker">
            <Workflow size={14} /> One clear review path
          </span>
          <div>
            <h2 id="review-path-title">From document packet to defensible decision.</h2>
            <p>
              ClaimLens keeps extraction, evidence, and reviewer action connected—so every finding
              can be understood and traced without leaving the workspace.
            </p>
          </div>
        </div>

        <div className="aero-path-grid">
          <article className="aero-step-card">
            <div className="aero-step-topline">
              <span>Step 01</span>
              <FileUp size={20} />
            </div>
            <h3>Upload the claim packet</h3>
            <p>Add the bill, discharge summary, and supporting reports as one review packet.</p>
            <div className="aero-step-preview aero-file-preview" aria-hidden="true">
              <FileText size={17} />
              <span>3 documents ready</span>
              <strong>PDF</strong>
            </div>
          </article>

          <article className="aero-step-card">
            <div className="aero-step-topline">
              <span>Step 02</span>
              <ScanText size={20} />
            </div>
            <h3>Follow every finding</h3>
            <p>Compare extracted values and open the exact document page behind each result.</p>
            <div className="aero-step-preview aero-evidence-preview" aria-hidden="true">
              <span>Invoice total</span>
              <strong>Page 3</strong>
              <i>98.4% confidence</i>
            </div>
          </article>

          <article className="aero-step-card">
            <div className="aero-step-topline">
              <span>Step 03</span>
              <ClipboardCheck size={20} />
            </div>
            <h3>Record the human decision</h3>
            <p>Acknowledge, resolve, or request evidence while preserving the review trail.</p>
            <div className="aero-step-preview aero-decision-preview" aria-hidden="true">
              <span>
                <Check size={14} /> Acknowledged
              </span>
              <strong>Reviewer controlled</strong>
            </div>
          </article>
        </div>

        <div className="aero-proof-strip">
          <div>
            <strong>Source-linked</strong>
            <span>Document, page, and extracted value stay together.</span>
          </div>
          <div>
            <strong>Evidence-aware</strong>
            <span>Missing support is shown as a gap—not a verdict.</span>
          </div>
          <div>
            <strong>Human-led</strong>
            <span>ClaimLens assists review; it never approves or pays a claim.</span>
          </div>
          <a href={reviewHref}>
            Open sample workspace <ArrowUpRight size={17} />
          </a>
        </div>
      </section>
      <CinematicReviewFooter reviewHref={reviewHref} />
      <footer className="aero-footer">
        <a href="/" className="aero-footer-brand" aria-label="ClaimLens home">
          <span>
            <ShieldCheck size={16} />
          </span>
          ClaimLens
        </a>
        <p>Synthetic claim-review prototype · Human decisions stay in reviewer control.</p>
        <nav aria-label="Footer navigation">
          <a href="#how-it-works" aria-label="Footer: How it works">
            How it works
          </a>
          <a href={loginHref} aria-label="Footer: Log in">
            Log in
          </a>
          <a href={reviewHref} aria-label="Footer: Workspace">
            Workspace
          </a>
        </nav>
        <small>© 2026 ClaimLens</small>
      </footer>
      {previewOpen && <SamplePreview reviewHref={reviewHref} close={() => setPreviewOpen(false)} />}
    </div>
  )
}

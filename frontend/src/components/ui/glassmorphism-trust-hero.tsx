import { useEffect, useRef, useState } from 'react'
import {
  ArrowRight,
  Play,
  Pause,
  Target,
  ShieldCheck,
  Sparkles,
  Database,
  ScanText,
  Workflow,
  LockKeyhole,
  Layers3,
  Cpu,
  X,
  FileText,
  Check,
} from 'lucide-react'
import { cn } from '@/lib/utils'

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
  backgroundImage?: string
  className?: string
}

const StatItem = ({ value, label }: { value: string; label: string }) => (
  <div className="flex cursor-default flex-col items-center justify-center gap-1.5 px-2 transition-transform hover:-translate-y-1">
    <span className="text-2xl font-semibold text-white">{value}</span>
    <span className="text-xs font-medium tracking-[0.16em] text-zinc-400 uppercase sm:text-xs">
      {label}
    </span>
  </div>
)

function SamplePreview({ reviewHref, close }: { reviewHref: string; close: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    dialog.current?.showModal()
  }, [])
  return (
    <dialog
      ref={dialog}
      onCancel={close}
      className="m-auto w-[calc(100%_-_2rem)] max-w-xl rounded-3xl border border-white/15 bg-zinc-950 p-7 text-white shadow-2xl backdrop:bg-black/80 backdrop:backdrop-blur-md sm:p-9"
      aria-labelledby="sample-title"
    >
      <div className="mb-7 flex items-center justify-between">
        <span className="flex items-center gap-2 text-xs tracking-[0.15em] text-amber-200 uppercase">
          <Sparkles size={14} />
          Synthetic demonstration
        </span>
        <button
          onClick={close}
          className="hero-link rounded-lg p-2 text-zinc-400 hover:bg-white/10 hover:text-white"
          aria-label="Close sample preview"
        >
          <X size={20} />
        </button>
      </div>
      <h2 id="sample-title" className="mb-3 text-3xl font-medium tracking-tight">
        From discrepancy
        <br />
        to the exact source.
      </h2>
      <p className="mb-7 text-sm leading-7 text-zinc-400">
        A fictional hospital bill shows a total that differs from its line items. ClaimLens brings
        both values into the review.
      </p>
      <div className="space-y-3 rounded-2xl border border-white/10 bg-white/5 p-5">
        <div className="flex items-center gap-2 text-xs text-zinc-400">
          <FileText size={15} />
          CityCare_itemized_bill.pdf · Page 3
        </div>
        <div className="flex justify-between gap-4 border-b border-white/10 py-3 text-sm">
          <span className="text-zinc-400">Stated invoice total</span>
          <strong className="font-medium">₹248,500.00</strong>
        </div>
        <div className="flex justify-between gap-4 border-b border-white/10 py-3 text-sm">
          <span className="text-zinc-400">Extracted line items</span>
          <strong className="font-medium">₹241,500.00</strong>
        </div>
        <div className="flex justify-between gap-4 pt-3 text-sm text-amber-200">
          <span>Difference to review</span>
          <strong className="font-semibold">₹7,000.00</strong>
        </div>
      </div>
      <p className="mt-5 flex items-start gap-2 text-xs leading-6 text-zinc-400">
        <ShieldCheck className="mt-1 shrink-0" size={15} />
        This finding asks for human review. It does not decide whether a claim should be paid.
      </p>
      <a
        href={reviewHref}
        className="hero-link mt-7 flex items-center justify-center gap-2 rounded-full bg-white px-6 py-3.5 text-sm font-semibold text-zinc-950 transition-colors hover:bg-amber-100"
      >
        Open review workspace
        <ArrowRight size={16} />
      </a>
    </dialog>
  )
}

export default function HeroSection({
  reviewHref = '/review',
  backgroundImage = '/images/hero-gold-waves.jpg',
  className,
}: HeroSectionProps) {
  const [previewOpen, setPreviewOpen] = useState(false)
  const [paused, setPaused] = useState(false)
  return (
    <div
      className={cn(
        'claimlens-hero relative isolate min-h-svh w-full overflow-hidden bg-zinc-950 font-sans text-white',
        className,
      )}
    >
      <div aria-hidden="true" className="hero-bg pointer-events-none absolute inset-0 -z-20">
        <img
          src={backgroundImage}
          alt=""
          className="h-full w-full object-cover object-center opacity-40"
          fetchPriority="high"
        />
        <div className="absolute inset-0 bg-linear-to-r from-zinc-950/90 via-zinc-950/55 to-zinc-950/20" />
        <div className="absolute inset-0 bg-linear-to-t from-zinc-950 via-transparent to-zinc-950/30" />
      </div>
      <div
        className="pointer-events-none absolute top-0 right-0 -z-10 h-[36rem] w-[45rem] rounded-full bg-amber-200/5 blur-[120px]"
        aria-hidden="true"
      />

      <header className="relative mx-auto flex w-full max-w-7xl items-center justify-between gap-5 border-b border-white/10 px-6 py-7 sm:px-10 lg:px-12">
        <a
          href="/"
          aria-label="ClaimLens home"
          className="hero-link flex items-center gap-2.5 text-xl font-semibold tracking-tight text-white no-underline"
        >
          <span className="flex size-8 items-center justify-center rounded-[10px] border border-white/20 bg-white/10 shadow-sm">
            <ShieldCheck size={19} />
          </span>
          ClaimLens
          <span className="ml-2 hidden border-l border-white/20 pl-4 text-xs font-normal tracking-[0.18em] text-zinc-400 uppercase sm:inline">
            Claim integrity
          </span>
        </a>
        <nav aria-label="Site navigation" className="flex items-center gap-6 sm:gap-9">
          <button
            onClick={() => setPreviewOpen(true)}
            className="hero-link hidden text-xs font-medium text-zinc-400 transition-colors hover:text-white sm:block"
          >
            How it works
          </button>
          <a
            href={reviewHref}
            className="hero-link inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-4 py-2.5 text-xs font-medium text-white no-underline backdrop-blur-md transition-colors hover:bg-white/10"
          >
            Open workspace
            <ArrowRight size={14} />
          </a>
        </nav>
      </header>

      <main className="relative mx-auto w-full max-w-7xl px-6 pt-14 pb-10 sm:px-10 sm:pt-20 lg:px-12 lg:pt-24 lg:pb-16">
        <div className="grid grid-cols-1 items-start gap-14 lg:grid-cols-12 lg:gap-12 xl:gap-16">
          <div className="flex flex-col justify-center space-y-8 pt-2 lg:col-span-7 lg:pt-5">
            <div className="hero-enter hero-delay-1">
              <div className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3.5 py-2 backdrop-blur-md transition-colors hover:bg-white/10">
                <span className="flex items-center gap-2 text-xs font-semibold tracking-[0.14em] text-zinc-300 uppercase">
                  <Sparkles className="size-3.5 text-[#ffcd75]" />
                  Clarity in every claim
                </span>
              </div>
            </div>
            <h1 className="hero-title hero-enter hero-delay-2 m-0 text-[clamp(2.2rem,8.4vw,4rem)] leading-[1.02] font-medium tracking-[-0.065em] text-white lg:text-[clamp(3.2rem,6.5vw,6rem)]">
              Every claim.
              <br />
              <span className="bg-linear-to-br from-white via-[#fff7e7] to-[#ffcd75] bg-clip-text text-transparent">
                Clear evidence.
              </span>
              <br />
              Confident review.
            </h1>
            <p className="hero-enter hero-delay-3 m-0 max-w-lg text-base leading-[1.85] font-normal text-zinc-400 sm:text-lg">
              Turn complex medical documents into a clear, traceable review. Spot discrepancies,
              inspect the source, and keep every decision in human hands.
            </p>
            <div className="hero-enter hero-delay-4 flex flex-col gap-3 pt-1 sm:flex-row sm:gap-4">
              <a
                href={reviewHref}
                className="hero-link group inline-flex items-center justify-center gap-3 rounded-full bg-white px-8 py-4 text-sm font-semibold text-zinc-950 no-underline transition-all hover:scale-[1.02] hover:bg-amber-50 active:scale-[0.98]"
              >
                Start reviewing
                <ArrowRight className="size-4 transition-transform group-hover:translate-x-1" />
              </a>
              <button
                onClick={() => setPreviewOpen(true)}
                className="hero-link group inline-flex items-center justify-center gap-3 rounded-full border border-white/15 bg-white/5 px-7 py-4 text-sm font-medium text-white backdrop-blur-sm transition-colors hover:border-white/25 hover:bg-white/10"
              >
                <Play className="size-3.5 fill-current" />
                Explore a sample
              </button>
            </div>
            <div className="hero-enter hero-delay-5 flex flex-wrap items-center gap-x-6 gap-y-3 pt-1 text-xs text-zinc-400">
              <span className="flex items-center gap-2">
                <Check size={13} className="text-zinc-400" />
                Source-linked findings
              </span>
              <span className="flex items-center gap-2">
                <Check size={13} className="text-zinc-400" />
                Human-led decisions
              </span>
            </div>
          </div>

          <div className="space-y-5 lg:col-span-5 lg:mt-9">
            <section
              aria-label="Synthetic packet preview"
              className="hero-glass hero-enter hero-delay-4 relative overflow-hidden rounded-3xl border border-white/15 bg-white/[0.045] p-7 backdrop-blur-xl sm:p-8"
            >
              <div
                className="pointer-events-none absolute -top-16 -right-16 h-64 w-64 rounded-full bg-white/5 blur-3xl"
                aria-hidden="true"
              />
              <div className="relative z-10">
                <div className="mb-7 flex items-center justify-between gap-4">
                  <span className="text-xs font-medium tracking-[0.16em] text-zinc-400 uppercase">
                    Inside a sample review
                  </span>
                  <span className="rounded-full border border-amber-200/15 bg-amber-200/5 px-2.5 py-1 text-xs font-medium tracking-wider text-amber-100/70 uppercase">
                    Synthetic data
                  </span>
                </div>
                <div className="mb-7 flex items-center gap-4">
                  <div className="flex size-12 shrink-0 items-center justify-center rounded-2xl bg-white/10 ring-1 ring-white/15">
                    <Target className="size-6 text-[#ffdc99]" />
                  </div>
                  <div>
                    <div className="text-4xl font-semibold tracking-tight text-white">
                      4
                      <span className="ml-2.5 text-base font-normal tracking-normal text-zinc-400">
                        integrity checks
                      </span>
                    </div>
                    <div className="mt-1 text-xs text-zinc-400">
                      One packet. A traceable path to the source.
                    </div>
                  </div>
                </div>
                <div className="mb-7 space-y-3">
                  <div className="flex justify-between text-xs">
                    <span className="text-zinc-400">Sample extraction quality</span>
                    <span className="font-medium text-white">94%</span>
                  </div>
                  <div
                    role="meter"
                    aria-label="Sample extraction quality"
                    aria-valuenow={94}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    className="h-1.5 w-full overflow-hidden rounded-full bg-white/10"
                  >
                    <div className="h-full w-[94%] rounded-full bg-linear-to-r from-white via-zinc-200 to-[#d7b575]" />
                  </div>
                </div>
                <div className="mb-6 h-px w-full bg-white/10" />
                <div className="grid grid-cols-3 divide-x divide-white/10 text-center">
                  <StatItem value="3" label="Documents" />
                  <StatItem value="2" label="Discrepancies" />
                  <StatItem value="1" label="Evidence request" />
                </div>
                <div className="mt-7 flex flex-wrap gap-2">
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium tracking-wider text-zinc-300 uppercase">
                    <ShieldCheck className="size-3 text-[#ffcd75]" />
                    Human review required
                  </span>
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium tracking-wider text-zinc-400 uppercase">
                    <Workflow className="size-3" />
                    Source-backed
                  </span>
                </div>
              </div>
            </section>

            <section
              aria-label="AWS architecture services"
              className={cn(
                'hero-glass hero-enter hero-delay-5 relative overflow-hidden rounded-3xl border border-white/10 bg-white/[0.035] py-6 backdrop-blur-xl',
                paused && 'hero-services-paused',
              )}
            >
              <div className="mb-6 flex items-center justify-between px-7">
                <h2 className="m-0 text-xs font-medium text-zinc-400">
                  Designed for the AWS stack
                </h2>
                <button
                  onClick={() => setPaused((value) => !value)}
                  aria-label={paused ? 'Play service animation' : 'Pause service animation'}
                  className="hero-link rounded p-1 text-zinc-400 transition-colors hover:text-white"
                >
                  {paused ? <Play size={12} /> : <Pause size={12} />}
                </button>
              </div>
              <div
                className="overflow-hidden"
                style={{
                  maskImage:
                    'linear-gradient(to right, transparent, black 12%, black 88%, transparent)',
                }}
              >
                <div className="hero-marquee flex">
                  {[0, 1].map((copy) => (
                    <div
                      className="flex shrink-0 items-center gap-9 pr-9"
                      key={copy}
                      aria-hidden={copy === 1}
                    >
                      {SERVICES.map((service) => (
                        <span
                          key={service.name}
                          className="flex shrink-0 cursor-default items-center gap-2 whitespace-nowrap text-zinc-400 transition-colors hover:text-white"
                        >
                          <service.icon className="size-5" strokeWidth={1.5} />
                          <span className="text-base font-medium tracking-tight">
                            {service.name}
                          </span>
                        </span>
                      ))}
                    </div>
                  ))}
                </div>
              </div>
            </section>
          </div>
        </div>
        <footer className="hero-enter hero-delay-5 mt-16 flex flex-wrap items-center justify-between gap-4 border-t border-white/10 pt-6 text-xs text-zinc-600 lg:mt-20">
          <span className="flex items-center gap-2">
            <ShieldCheck size={13} />
            Evidence for review. Decisions stay with people.
          </span>
          <span>ClaimLens · Hackathon prototype</span>
        </footer>
      </main>
      {previewOpen && <SamplePreview reviewHref={reviewHref} close={() => setPreviewOpen(false)} />}
    </div>
  )
}

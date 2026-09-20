import { useLayoutEffect, useRef } from 'react'
import { CheckCircle2, FileText, ScanText, ShieldCheck } from 'lucide-react'
import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'

if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
  gsap.registerPlugin(ScrollTrigger)
}

export function CinematicReviewFooter({ reviewHref }: { reviewHref: string }) {
  const sectionRef = useRef<HTMLElement>(null)

  useLayoutEffect(() => {
    const section = sectionRef.current
    if (
      !section ||
      typeof window.matchMedia !== 'function' ||
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    )
      return
    const desktop = window.matchMedia('(min-width: 768px)').matches
    const ctx = gsap.context(() => {
      const cards = gsap.utils.toArray<HTMLElement>('.cinematic-review-card')
      gsap.set(cards, { autoAlpha: 0, y: 52, rotateX: -10 })
      gsap.set('.cinematic-review-copy', { autoAlpha: 0, y: 32 })
      const timeline = gsap.timeline(
        desktop
          ? {
              scrollTrigger: {
                trigger: section,
                start: 'top top',
                end: '+=1700',
                pin: true,
                scrub: 0.8,
              },
            }
          : { scrollTrigger: { trigger: section, start: 'top 78%', once: true } },
      )
      timeline
        .to('.cinematic-review-copy', { autoAlpha: 1, y: 0, duration: 0.65, ease: 'power3.out' })
        .to(
          cards,
          { autoAlpha: 1, y: 0, rotateX: 0, duration: 0.8, stagger: 0.18, ease: 'power3.out' },
          '-=0.2',
        )
        .to(
          '.cinematic-review-meter > i',
          { scaleX: 1, duration: 0.9, ease: 'power2.out' },
          '-=0.35',
        )
        .to(
          '.cinematic-review-outcome',
          { autoAlpha: 1, y: 0, duration: 0.55, ease: 'back.out(1.4)' },
          '-=0.2',
        )
    }, section)
    return () => ctx.revert()
  }, [])

  return (
    <section ref={sectionRef} className="cinematic-review" aria-labelledby="cinematic-review-title">
      <div className="cinematic-review-grid" aria-hidden="true" />
      <div className="cinematic-review-inner">
        <div className="cinematic-review-copy">
          <span>Evidence in motion</span>
          <h2 id="cinematic-review-title">Follow the record to a defensible review.</h2>
          <p>
            Every stage stays linked to source evidence, while the final decision stays with the
            reviewer.
          </p>
        </div>
        <div className="cinematic-review-cards">
          <article className="cinematic-review-card">
            <FileText size={21} />
            <span>01 · Intake</span>
            <strong>Claim packet</strong>
            <small>Bill, summary, and reports stay together.</small>
          </article>
          <article className="cinematic-review-card cinematic-review-focus">
            <ScanText size={21} />
            <span>02 · Evidence</span>
            <strong>Invoice total</strong>
            <small>CityCare bill · Page 3</small>
            <div className="cinematic-review-meter">
              <i />
            </div>
            <em>98.4% extraction confidence</em>
          </article>
          <article className="cinematic-review-card">
            <ShieldCheck size={21} />
            <span>03 · Review</span>
            <strong>Human decision</strong>
            <small>Acknowledge, resolve, or request evidence.</small>
          </article>
        </div>
        <div className="cinematic-review-outcome">
          <CheckCircle2 size={18} />
          <span>Reviewer controlled</span>
          <a href={reviewHref}>Open sample workspace</a>
        </div>
      </div>
    </section>
  )
}

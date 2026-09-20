import { useLayoutEffect, useRef } from 'react'
import { BadgeCheck, FileText, ScanText, ShieldCheck } from 'lucide-react'
import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'

if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
  gsap.registerPlugin(ScrollTrigger)
}

export function CinematicReviewFooter({ reviewHref }: { reviewHref: string }) {
  const sectionRef = useRef<HTMLElement>(null)

  useLayoutEffect(() => {
    const section = sectionRef.current
    if (!section || typeof window.matchMedia !== 'function') return

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const desktop = window.matchMedia('(min-width: 768px)').matches
    if (reducedMotion) return

    const ctx = gsap.context(() => {
      const q = gsap.utils.selector(section)
      const phone = q('.cinematic-review-phone')[0]
      const notifications = q('.cinematic-review-note')
      const widgets = q('.cinematic-review-widget')

      gsap.set(q('.cinematic-review-intro'), { autoAlpha: 0, y: 42, filter: 'blur(16px)' })
      gsap.set(q('.cinematic-review-stage'), { y: window.innerHeight * 0.95, autoAlpha: 1 })
      gsap.set(phone, { y: 270, rotationX: 38, rotationY: -18, scale: 0.72, autoAlpha: 0 })
      gsap.set(widgets, { y: 24, scale: 0.94, autoAlpha: 0 })
      gsap.set(notifications, { y: 56, scale: 0.8, rotate: -7, autoAlpha: 0 })
      gsap.set(q('.cinematic-review-sidecopy, .cinematic-review-wordmark'), { autoAlpha: 0 })
      gsap.set(q('.cinematic-review-outro'), { autoAlpha: 0, scale: 0.86, filter: 'blur(18px)' })

      const timeline = gsap.timeline({
        scrollTrigger: desktop
          ? {
              trigger: section,
              start: 'top top',
              end: '+=4600',
              pin: true,
              scrub: 0.9,
              anticipatePin: 1,
            }
          : { trigger: section, start: 'top 76%', once: true },
      })

      timeline
        .to(q('.cinematic-review-intro'), {
          autoAlpha: 1,
          y: 0,
          filter: 'blur(0px)',
          duration: 0.85,
          ease: 'expo.out',
        })
        .to(q('.cinematic-review-intro'), {
          autoAlpha: 0,
          scale: 1.08,
          filter: 'blur(14px)',
          duration: 0.9,
          ease: 'power2.inOut',
        })
        .to(q('.cinematic-review-stage'), { y: 0, duration: 1.1, ease: 'power3.inOut' }, '<')
        .to(q('.cinematic-review-stage'), {
          width: '100%',
          height: '100%',
          borderRadius: 0,
          duration: 0.95,
          ease: 'power3.inOut',
        })
        .to(phone, {
          y: 0,
          rotationX: 0,
          rotationY: 0,
          scale: 1,
          autoAlpha: 1,
          duration: 1.45,
          ease: 'expo.out',
        })
        .to(widgets, { y: 0, scale: 1, autoAlpha: 1, stagger: 0.12, duration: 0.55 }, '<+=0.25')
        .to(
          q('.cinematic-review-ring'),
          { strokeDashoffset: 58, duration: 1.2, ease: 'power3.inOut' },
          '<+=0.1',
        )
        .to(
          q('.cinematic-review-count'),
          { textContent: 98, snap: { textContent: 1 }, duration: 1.15 },
          '<',
        )
        .to(
          notifications,
          {
            y: 0,
            scale: 1,
            rotate: 0,
            autoAlpha: 1,
            stagger: 0.17,
            duration: 0.65,
            ease: 'back.out(1.4)',
          },
          '<+=0.38',
        )
        .to(
          q('.cinematic-review-sidecopy'),
          { x: 0, autoAlpha: 1, duration: 0.7, ease: 'power4.out' },
          '<+=0.15',
        )
        .to(
          q('.cinematic-review-wordmark'),
          { x: 0, autoAlpha: 0.92, duration: 0.75, ease: 'expo.out' },
          '<',
        )
        .to({}, { duration: 0.8 })
        .to(
          [
            phone,
            ...notifications,
            ...widgets,
            ...q('.cinematic-review-sidecopy, .cinematic-review-wordmark'),
          ],
          { y: -58, scale: 0.88, autoAlpha: 0, duration: 0.8, stagger: 0.03, ease: 'power3.in' },
        )
        .to(
          q('.cinematic-review-outro'),
          { autoAlpha: 1, scale: 1, filter: 'blur(0px)', duration: 0.85, ease: 'expo.out' },
          '<+=0.35',
        )
    }, section)

    return () => ctx.revert()
  }, [])

  return (
    <section ref={sectionRef} className="cinematic-review" aria-labelledby="cinematic-review-title">
      <div className="cinematic-review-grid" aria-hidden="true" />
      <div className="cinematic-review-intro">
        <span>Claim integrity, in focus</span>
        <h2 id="cinematic-review-title">Follow every finding.</h2>
        <p>Scroll to see the review record come to life.</p>
      </div>
      <div className="cinematic-review-stage" aria-label="A ClaimLens evidence review preview">
        <div className="cinematic-review-sheen" aria-hidden="true" />
        <div className="cinematic-review-sidecopy">
          <span>Evidence-aware review</span>
          <h3>Every record, connected.</h3>
          <p>Bring the bill, summary, and supporting reports into one human-led review trail.</p>
        </div>
        <strong className="cinematic-review-wordmark" aria-hidden="true">
          CLAIMLENS
        </strong>
        <div className="cinematic-review-phone-wrap">
          <div className="cinematic-review-phone">
            <i className="cinematic-review-side-button cinematic-review-side-button-one" />
            <i className="cinematic-review-side-button cinematic-review-side-button-two" />
            <i className="cinematic-review-side-button cinematic-review-side-button-three" />
            <div className="cinematic-review-screen">
              <div className="cinematic-review-island">
                <b />
              </div>
              <div className="cinematic-review-apphead cinematic-review-widget">
                <div>
                  <span>Review today</span>
                  <strong>CityCare packet</strong>
                </div>
                <b>CL</b>
              </div>
              <div className="cinematic-review-score cinematic-review-widget">
                <svg viewBox="0 0 144 144" aria-hidden="true">
                  <circle cx="72" cy="72" r="58" />
                  <circle className="cinematic-review-ring" cx="72" cy="72" r="58" />
                </svg>
                <div>
                  <strong className="cinematic-review-count">0</strong>
                  <span>evidence match</span>
                </div>
              </div>
              <div className="cinematic-review-widget cinematic-review-row">
                <FileText size={17} />
                <div>
                  <b>Invoice total</b>
                  <span>Page 3 · matched</span>
                </div>
                <BadgeCheck size={16} />
              </div>
              <div className="cinematic-review-widget cinematic-review-row">
                <ShieldCheck size={17} />
                <div>
                  <b>Human review</b>
                  <span>Decision stays with you</span>
                </div>
                <BadgeCheck size={16} />
              </div>
              <i className="cinematic-review-homebar" />
            </div>
          </div>
          <div className="cinematic-review-note cinematic-review-note-top">
            <ScanText size={18} />
            <div>
              <b>Source found</b>
              <span>Invoice total · page 3</span>
            </div>
          </div>
          <div className="cinematic-review-note cinematic-review-note-bottom">
            <BadgeCheck size={18} />
            <div>
              <b>Evidence linked</b>
              <span>Ready for reviewer action</span>
            </div>
          </div>
        </div>
      </div>
      <div className="cinematic-review-outro">
        <span>Human-led, source-linked</span>
        <h2>A defensible decision starts with the record.</h2>
        <p>ClaimLens highlights the evidence. Your reviewer makes the call.</p>
        <a href={reviewHref}>
          Open sample workspace <span aria-hidden="true">↗</span>
        </a>
      </div>
    </section>
  )
}

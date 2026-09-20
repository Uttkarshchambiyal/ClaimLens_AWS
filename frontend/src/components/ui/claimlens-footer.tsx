import { useLayoutEffect, useRef } from 'react'
import { Code2, Contact, Mail, ShieldCheck } from 'lucide-react'
import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'

if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
  gsap.registerPlugin(ScrollTrigger)
}

interface ClaimLensFooterProps {
  loginHref: string
  reviewHref: string
}

const footerLinks = [
  { label: 'How it works', href: '#how-it-works' },
  { label: 'Log in', href: 'login' },
  { label: 'Workspace', href: 'workspace' },
]

export function ClaimLensFooter({ loginHref, reviewHref }: ClaimLensFooterProps) {
  const footerRef = useRef<HTMLElement>(null)

  useLayoutEffect(() => {
    const footer = footerRef.current
    if (!footer || typeof window.matchMedia !== 'function') return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return

    const ctx = gsap.context(() => {
      gsap.from('.claimlens-footer-reveal', {
        autoAlpha: 0,
        y: 22,
        stagger: 0.1,
        duration: 0.65,
        ease: 'power3.out',
        scrollTrigger: { trigger: footer, start: 'top 88%', once: true },
      })
      gsap.to('.claimlens-footer-pattern', {
        backgroundPositionX: '120px',
        duration: 12,
        repeat: -1,
        ease: 'none',
      })
    }, footer)

    return () => ctx.revert()
  }, [])

  return (
    <footer ref={footerRef} className="claimlens-footer">
      <div className="claimlens-footer-main">
        <a
          className="claimlens-footer-logo claimlens-footer-reveal"
          href="/"
          aria-label="ClaimLens home"
        >
          <span>
            <ShieldCheck size={19} />
          </span>
          <b>ClaimLens</b>
        </a>
        <p className="claimlens-footer-reveal">
          Synthetic claim-review prototype. Every decision stays in reviewer control.
        </p>
        <nav
          className="claimlens-footer-nav claimlens-footer-reveal"
          aria-label="Footer navigation"
        >
          {footerLinks.map(({ label, href }) => {
            const destination =
              href === 'login' ? loginHref : href === 'workspace' ? reviewHref : href
            return (
              <a key={label} href={destination} aria-label={`Footer: ${label}`}>
                {label}
              </a>
            )
          })}
        </nav>
        <div
          className="claimlens-footer-social claimlens-footer-reveal"
          aria-label="ClaimLens social links"
        >
          <a
            href="https://github.com/Uttkarshchambiyal"
            target="_blank"
            rel="noreferrer"
            aria-label="ClaimLens on GitHub"
          >
            <Code2 size={16} />
          </a>
          <a
            href="https://www.linkedin.com/in/uttkarshchambiyal/"
            target="_blank"
            rel="noreferrer"
            aria-label="ClaimLens on LinkedIn"
          >
            <Contact size={16} />
          </a>
          <a href="mailto:hello@claimlens.example" aria-label="Email ClaimLens">
            <Mail size={16} />
          </a>
        </div>
      </div>
      <div className="claimlens-footer-pattern" aria-hidden="true" />
      <div className="claimlens-footer-bottom claimlens-footer-reveal">
        <span>© {new Date().getFullYear()} ClaimLens</span>
        <span>Evidence-aware · Human-led</span>
      </div>
    </footer>
  )
}

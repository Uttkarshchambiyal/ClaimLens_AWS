import React, { lazy, Suspense } from 'react'
import ReactDOM from 'react-dom/client'
import HeroDemo from '@/components/demo'
import './hero.css'

const ReviewApp = lazy(() => import('./App').then((module) => ({ default: module.App })))
const isReview =
  /^\/review\/?$/.test(window.location.pathname) ||
  window.location.pathname.startsWith('/auth/') ||
  new URLSearchParams(window.location.search).has('analysis')

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {isReview ? (
      <Suspense
        fallback={
          <div role="status" className="route-loading">
            Opening review workspace…
          </div>
        }
      >
        <ReviewApp />
      </Suspense>
    ) : (
      <HeroDemo />
    )}
  </React.StrictMode>,
)

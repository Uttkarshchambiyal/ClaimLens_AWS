import React, { lazy, Suspense } from 'react'
import ReactDOM from 'react-dom/client'
import HeroDemo from '@/components/demo'
import { AuthPage } from '@/components/AuthPage'
import { ThemeProvider } from '@/components/ui/theme-provider'
import './hero.css'

const ReviewApp = lazy(() => import('./App').then((module) => ({ default: module.App })))
const authMode =
  window.location.pathname === '/auth/signup'
    ? 'signup'
    : window.location.pathname === '/auth/login'
      ? 'login'
      : null
const isReview =
  /^\/review\/?$/.test(window.location.pathname) ||
  window.location.pathname === '/auth/callback' ||
  new URLSearchParams(window.location.search).has('analysis')

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider defaultTheme="light" enableSystem storageKey="claimlens-theme">
      {authMode ? (
        <AuthPage mode={authMode} />
      ) : isReview ? (
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
    </ThemeProvider>
  </React.StrictMode>,
)

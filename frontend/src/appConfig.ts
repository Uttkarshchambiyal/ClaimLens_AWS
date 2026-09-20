export type AppMode = 'mock' | 'production'

const configuredMode =
  import.meta.env.VITE_APP_MODE || (import.meta.env.DEV ? 'mock' : 'production')

export const appMode: AppMode = configuredMode === 'mock' ? 'mock' : 'production'
export const isValidAppMode = ['mock', 'production'].includes(configuredMode)

// The public judging route deliberately uses only bundled fictional evidence.
// It is never uploaded, sent to AWS, or presented as a live extraction.
export const isGuidedSample =
  typeof window !== 'undefined' &&
  (window.location.pathname.replace(/\/+$/, '') === '/sample' ||
    new URLSearchParams(window.location.search).get('sample') === '1')
export const usesLocalDemo = appMode === 'mock' || isGuidedSample

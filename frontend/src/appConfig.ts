export type AppMode = 'mock' | 'production'

const configuredMode =
  import.meta.env.VITE_APP_MODE || (import.meta.env.DEV ? 'mock' : 'production')

export const appMode: AppMode = configuredMode === 'mock' ? 'mock' : 'production'
export const isValidAppMode = ['mock', 'production'].includes(configuredMode)

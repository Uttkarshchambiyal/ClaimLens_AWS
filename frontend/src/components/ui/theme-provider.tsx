import {
  createContext,
  useContext,
  useLayoutEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

type Theme = 'dark' | 'light'
type ThemeContextValue = { resolvedTheme: Theme; setTheme: (theme: Theme) => void }

const ThemeContext = createContext<ThemeContextValue>({
  resolvedTheme: 'light',
  setTheme: () => undefined,
})

function preferredTheme(defaultTheme: Theme, enableSystem: boolean, storageKey: string): Theme {
  if (typeof window === 'undefined') return defaultTheme
  const stored = window.localStorage.getItem(storageKey)
  if (stored === 'dark' || stored === 'light') return stored
  if (enableSystem && window.matchMedia('(prefers-color-scheme: light)').matches) return 'light'
  return defaultTheme
}

export function ThemeProvider({
  children,
  defaultTheme = 'light',
  enableSystem = true,
  storageKey = 'claimlens-theme',
}: {
  children: ReactNode
  defaultTheme?: Theme
  enableSystem?: boolean
  storageKey?: string
}) {
  const [resolvedTheme, setResolvedTheme] = useState<Theme>(() =>
    preferredTheme(defaultTheme, enableSystem, storageKey),
  )

  useLayoutEffect(() => {
    const root = document.documentElement
    root.classList.remove('light', 'dark')
    root.classList.add(resolvedTheme)
    root.style.colorScheme = resolvedTheme
    window.localStorage.setItem(storageKey, resolvedTheme)
  }, [resolvedTheme, storageKey])

  const value = useMemo(() => ({ resolvedTheme, setTheme: setResolvedTheme }), [resolvedTheme])
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export const useClaimLensTheme = () => useContext(ThemeContext)

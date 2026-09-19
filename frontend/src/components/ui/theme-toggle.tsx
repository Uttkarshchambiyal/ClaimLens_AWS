import { useEffect, useState } from 'react'
import { Moon, Sun } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useClaimLensTheme } from '@/components/ui/theme-provider'

export function ThemeToggle({ className }: { className?: string }) {
  const { resolvedTheme, setTheme } = useClaimLensTheme()
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])
  const dark = !mounted || resolvedTheme !== 'light'
  return (
    <button
      type="button"
      className={cn('theme-toggle', className)}
      onClick={() => setTheme(dark ? 'light' : 'dark')}
      aria-label={dark ? 'Use light theme' : 'Use dark theme'}
      title={dark ? 'Use light theme' : 'Use dark theme'}
    >
      {dark ? <Sun size={18} /> : <Moon size={18} />}
    </button>
  )
}

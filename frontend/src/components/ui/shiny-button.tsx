import type React from 'react'
import { cn } from '@/lib/utils'
import './shiny-button.css'

interface ShinyButtonProps {
  children: React.ReactNode
  onClick?: () => void
  className?: string
  compact?: boolean
  'aria-label'?: string
}

export function ShinyButton({
  children,
  onClick,
  className = '',
  compact = false,
  ...rest
}: ShinyButtonProps) {
  return (
    <button
      className={cn('shiny-cta', compact && 'shiny-cta-compact', className)}
      onClick={onClick}
      {...rest}
    >
      <span>{children}</span>
    </button>
  )
}

export default ShinyButton

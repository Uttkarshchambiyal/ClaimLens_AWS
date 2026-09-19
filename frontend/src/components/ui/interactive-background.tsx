import { lazy, Suspense } from 'react'
import type { InteractiveBackgroundProps } from './interactive-hero-backgrounds'
import { cn } from '@/lib/utils'

const InteractiveCanvas = lazy(() =>
  import('./interactive-hero-backgrounds').then((module) => ({
    default: module.InteractiveBackground,
  })),
)

export function InteractiveBackground(props: InteractiveBackgroundProps) {
  return (
    <Suspense
      fallback={
        <div
          className={cn(
            'interactive-background interactive-background-fallback',
            props.subtle && 'interactive-background-subtle',
            props.className,
          )}
          aria-hidden="true"
        >
          <div className="interactive-background-glow" />
          <div className="interactive-background-vignette" />
        </div>
      }
    >
      <InteractiveCanvas {...props} />
    </Suspense>
  )
}

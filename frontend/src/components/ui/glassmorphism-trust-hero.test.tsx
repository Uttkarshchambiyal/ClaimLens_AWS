import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import HeroSection from './glassmorphism-trust-hero'

describe('ClaimLens opening hero', () => {
  it('routes calls to action to the reviewer workspace and labels sample metrics', () => {
    render(<HeroSection reviewHref="/review?analysis=sample" />)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Every claim.')
    expect(screen.getByRole('link', { name: 'Start reviewing' })).toHaveAttribute(
      'href',
      '/review?analysis=sample',
    )
    expect(screen.getByText('Synthetic data')).toBeVisible()
    expect(screen.getByRole('meter', { name: 'Sample extraction quality' })).toHaveAttribute(
      'aria-valuenow',
      '94',
    )
    expect(screen.queryByText('Trusted by Industry Leaders')).not.toBeInTheDocument()
  })

  it('opens and closes an accessible sample with explicit human-review boundaries', async () => {
    const user = userEvent.setup()
    render(<HeroSection />)
    await user.click(screen.getByRole('button', { name: 'Explore a sample' }))
    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByText('₹7,000.00')).toBeVisible()
    expect(within(dialog).getByText(/does not decide whether a claim should be paid/)).toBeVisible()
    expect(within(dialog).getByRole('link', { name: 'Open review workspace' })).toHaveAttribute(
      'href',
      '/review',
    )
    await user.click(within(dialog).getByRole('button', { name: 'Close sample preview' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'How it works' }))
    expect(screen.getByRole('dialog')).toBeVisible()
  })

  it('lets the reviewer pause the decorative animation', async () => {
    const user = userEvent.setup()
    render(<HeroSection />)
    await user.click(screen.getByRole('button', { name: 'Pause service animation' }))
    expect(screen.getByRole('region', { name: 'AWS architecture services' })).toHaveClass(
      'hero-services-paused',
    )
    await user.click(screen.getByRole('button', { name: 'Play service animation' }))
    expect(screen.getByRole('region', { name: 'AWS architecture services' })).not.toHaveClass(
      'hero-services-paused',
    )
  })
})

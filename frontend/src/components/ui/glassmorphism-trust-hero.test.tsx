import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import HeroSection from './glassmorphism-trust-hero'

describe('ClaimLens opening hero', () => {
  it('keeps the landing page public and offers explicit account actions', () => {
    render(<HeroSection reviewHref="/review?analysis=sample" />)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Every claim.')
    expect(screen.getByRole('link', { name: 'Create your account' })).toHaveAttribute(
      'href',
      '/auth/signup',
    )
    expect(screen.getAllByRole('link', { name: 'Log in' })).toHaveLength(2)
    expect(screen.getByRole('link', { name: 'Create account' })).toHaveAttribute(
      'href',
      '/auth/signup',
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
    expect(screen.getByRole('link', { name: 'How it works' })).toHaveAttribute(
      'href',
      '#how-it-works',
    )
    expect(
      screen.getByRole('heading', { name: /document packet to defensible decision/i }),
    ).toBeVisible()
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

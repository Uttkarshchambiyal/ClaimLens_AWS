import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App } from './App'
import { SourceViewer } from './components/SourceViewer'
import { demoAnalysis } from './mockData'
import { demoSave } from './demoStore'

beforeEach(() => {
  window.history.replaceState({}, '', '/review?analysis=' + demoAnalysis.id)
  window.sessionStorage.clear()
  demoSave(structuredClone(demoAnalysis))
})
afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('connected review flows', () => {
  it('keeps queue search out of the review and restores navigation from the URL', async () => {
    const user = userEvent.setup()
    render(<App />)
    await screen.findByRole('heading', { name: 'Invoice total does not reconcile' })
    expect(screen.getByRole('link', { name: 'ClaimLens home' })).toHaveAttribute('href', '/')
    await user.click(screen.getByRole('button', { name: 'Dashboard' }))
    expect(screen.getByRole('heading', { name: 'Review dashboard' })).toBeVisible()
    expect(screen.getByRole('heading', { name: 'See the workload at a glance' })).toBeVisible()
    expect(screen.getByRole('heading', { name: 'One transparent review path' })).toBeVisible()
    expect(window.location.search).toContain('view=dashboard')
    await user.click(screen.getByRole('button', { name: 'Review queue' }))
    expect(window.location.search).toContain('view=queue')
    await user.type(screen.getByRole('textbox', { name: 'Search packets' }), 'nothing here')
    expect(screen.getByText('No packets found')).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Claim review' }))
    expect(screen.getByRole('heading', { name: 'Invoice total does not reconcile' })).toBeVisible()
    expect(screen.getByRole('textbox', { name: 'Search findings' })).toHaveValue('')
    window.history.replaceState({}, '', '/review?view=activity&analysis=' + demoAnalysis.id)
    fireEvent.popState(window)
    expect(await screen.findByRole('heading', { name: 'Review activity' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Review activity' })).toHaveAttribute(
      'aria-current',
      'page',
    )
  })

  it('supports keyboard tabs and document-to-evidence navigation', async () => {
    const user = userEvent.setup()
    render(<App />)
    await screen.findByRole('heading', { name: 'Invoice total does not reconcile' })
    screen.getByRole('tab', { name: /Findings/ }).focus()
    await user.keyboard('{ArrowRight}')
    expect(screen.getByRole('tab', { name: /Documents/ })).toHaveFocus()
    await user.keyboard('{End}')
    expect(screen.getByRole('tab', { name: 'Insights' })).toHaveFocus()
    expect(screen.getByRole('heading', { name: 'Review insights' })).toBeVisible()
    await user.keyboard('{Home}')
    await user.click(screen.getByRole('tab', { name: /Documents/ }))
    const documents = screen.getByRole('tabpanel', { name: /Documents/ })
    await user.click(within(documents).getAllByRole('button', { name: 'View evidence' })[0])
    expect(screen.getByRole('dialog', { name: 'Document source viewer' })).toBeVisible()
    expect(screen.getByRole('tab', { name: /Findings/ })).toHaveAttribute('aria-selected', 'true')
    await user.click(screen.getByRole('button', { name: 'Zoom out' }))
    expect(
      within(screen.getByRole('dialog', { name: 'Document source viewer' })).getByText('75%'),
    ).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Reset zoom' }))
    expect(
      within(screen.getByRole('dialog', { name: 'Document source viewer' })).getByText('100%'),
    ).toBeVisible()
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog', { name: 'Document source viewer' })).not.toBeInTheDocument()
  })

  it('submits an uploaded packet through the dialog without fabricating extraction', async () => {
    const user = userEvent.setup()
    render(<App />)
    await screen.findByRole('heading', { name: 'Invoice total does not reconcile' })
    await user.click(screen.getByRole('button', { name: 'New packet' }))
    const dialog = screen.getByRole('dialog', { name: 'Start a new review' })
    await user.upload(
      within(dialog).getByLabelText('Claim documents'),
      new File(['%PDF synthetic'], 'synthetic-bill.pdf', { type: 'application/pdf' }),
    )
    await user.click(within(dialog).getByRole('button', { name: 'Start review' }))
    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: 'Start a new review' })).not.toBeInTheDocument(),
    )
    expect(screen.getAllByText('Check unavailable').length).toBeGreaterThan(0)
    expect(
      screen.getByText(
        'No reliable source was extracted for this check. The result is not a clean pass.',
      ),
    ).toBeVisible()
    expect(window.location.search).toContain('analysis=local_')
  })

  it('opens the guide and downloads the latest report through the export button', async () => {
    const user = userEvent.setup()
    const createUrl = vi.fn(() => 'blob:synthetic-report')
    vi.stubGlobal(
      'URL',
      class extends URL {
        static createObjectURL = createUrl
        static revokeObjectURL = vi.fn()
      },
    )
    const download = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    render(<App />)
    await screen.findByRole('heading', { name: 'Invoice total does not reconcile' })
    await user.click(screen.getByRole('button', { name: 'Open review guide' }))
    expect(screen.getByRole('dialog', { name: 'Review with confidence' })).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Close review guide' }))
    await user.click(screen.getByRole('button', { name: 'Export report' }))
    await screen.findByText('Review report exported.')
    expect(createUrl).toHaveBeenCalledWith(expect.any(Blob))
    expect(download).toHaveBeenCalledOnce()
    expect(download.mock.instances[0]).toHaveAttribute(
      'download',
      demoAnalysis.claimId + '-review-v1.json',
    )
    vi.unstubAllGlobals()
  })

  it('keeps source evidence available after a failed correction and allows retry', async () => {
    const user = userEvent.setup()
    const onCorrect = vi
      .fn()
      .mockRejectedValueOnce(new Error('Save temporarily unavailable'))
      .mockResolvedValueOnce(undefined)
    render(
      <SourceViewer
        analysis={demoAnalysis}
        evidence={demoAnalysis.findings[0].evidence[0]}
        onClose={() => {}}
        onCorrect={onCorrect}
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Correct extraction' }))
    await user.type(screen.getByRole('textbox', { name: 'Corrected value' }), '241500')
    await user.click(screen.getByRole('button', { name: 'Save correction' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Save temporarily unavailable')
    expect(screen.getByText('Synthetic evidence sheet · not an uploaded PDF')).toBeVisible()
    expect(screen.getByRole('textbox', { name: 'Corrected value' })).toHaveValue('241500')
    await user.click(screen.getByRole('button', { name: 'Save correction' }))
    await waitFor(() =>
      expect(screen.queryByRole('textbox', { name: 'Corrected value' })).not.toBeInTheDocument(),
    )
    expect(onCorrect).toHaveBeenCalledTimes(2)
  })
})

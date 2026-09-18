import { beforeEach, describe, expect, it } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { App } from './App'
import { demoAnalysis } from './mockData'
import { demoGet, demoSave } from './demoStore'
import { createAnalysis, getReport, validateUploads } from './api'

beforeEach(() => {
  window.history.replaceState({}, '', '/')
  demoSave(structuredClone(demoAnalysis))
})

describe('review workspace', () => {
  it('shows the finding matching the selected filter and handles empty searches', async () => {
    const user = userEvent.setup()
    render(<App />)
    await screen.findByRole('heading', { name: 'Invoice total does not reconcile' })
    await user.click(screen.getByRole('button', { name: 'Passed' }))
    expect(screen.getByRole('heading', { name: 'Patient identifiers align' })).toBeInTheDocument()
    expect(
      screen.queryByRole('heading', { name: 'Invoice total does not reconcile' }),
    ).not.toBeInTheDocument()
    await user.type(screen.getByRole('textbox', { name: 'Search findings' }), 'no such finding')
    expect(screen.getByText('No matching checks')).toBeInTheDocument()
    expect(
      screen.queryByRole('heading', { name: 'Patient identifiers align' }),
    ).not.toBeInTheDocument()
  })
  it('persists dispositions in the analysis and exported report', async () => {
    const user = userEvent.setup()
    render(<App />)
    await screen.findByRole('heading', { name: 'Invoice total does not reconcile' })
    await user.click(screen.getByRole('button', { name: 'Resolved' }))
    await screen.findByText('Review disposition saved.')
    expect(demoGet(demoAnalysis.id).findings[0].reviewerAction).toBe('RESOLVED')
    const report = (await getReport(demoAnalysis.id)) as { analysis: typeof demoAnalysis }
    expect(report.analysis.findings[0].reviewerAction).toBe('RESOLVED')
    await user.click(screen.getByRole('button', { name: 'Review activity' }))
    expect(screen.getByText('Marked resolved')).toBeInTheDocument()
  })
  it('opens evidence and saves a correction without replacing the source', async () => {
    const user = userEvent.setup()
    render(<App />)
    await screen.findByRole('heading', { name: 'Invoice total does not reconcile' })
    await user.click(screen.getByRole('button', { name: /View source A, CityCare_itemized_bill/ }))
    expect(screen.getByText('Synthetic evidence sheet · not an uploaded PDF')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Correct extraction' }))
    await user.type(screen.getByRole('textbox', { name: 'Corrected value' }), '241500.00')
    await user.click(screen.getByRole('button', { name: 'Save correction' }))
    await waitFor(() => expect(demoGet(demoAnalysis.id).corrections).toHaveLength(1))
    expect(demoGet(demoAnalysis.id).findings[0].evidence[0].excerpt).toBe(
      'Invoice Total ₹248,500.00',
    )
  })
  it('opens a different packet from the queue', async () => {
    const user = userEvent.setup()
    render(<App />)
    await screen.findByRole('heading', { name: 'Invoice total does not reconcile' })
    await user.click(screen.getByRole('button', { name: /Review queue/ }))
    await user.click(screen.getByRole('button', { name: 'Open CLM-20483' }))
    expect(
      await screen.findByRole('heading', { name: 'Decimal separator needs confirmation' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Not provided')).toBeInTheDocument()
  })
})

describe('packet uploads', () => {
  it('requires one bill, allowed formats, and a bounded file size', () => {
    expect(validateUploads([])).toMatch(/bill/)
    const file = new File(['data'], 'file.txt', { type: 'text/plain' })
    expect(validateUploads([{ file, type: 'BILL' }])).toMatch(/PDF/)
    const pdf = new File(['%PDF'], 'bill.pdf', { type: 'application/pdf' })
    expect(validateUploads([{ file: pdf, type: 'SUPPORTING_REPORT' }])).toMatch(/exactly one/)
    expect(validateUploads([{ file: pdf, type: 'BILL' }])).toBeNull()
  })
  it('never invents an extraction for uploaded files in mock mode', async () => {
    const file = new File(['%PDF'], 'bill.pdf', { type: 'application/pdf' })
    const first = await createAnalysis(
      [{ file, type: 'BILL' }],
      undefined,
      'test-duplicate',
      () => {},
    )
    const retry = await createAnalysis(
      [{ file, type: 'BILL' }],
      undefined,
      'test-duplicate',
      () => {},
    )
    expect(first.analysisId).toBe(retry.analysisId)
    const analysis = demoGet(first.analysisId)
    expect(analysis.findings[0].status).toBe('ERROR')
    expect(analysis.findings[0].evidence).toHaveLength(0)
    expect(analysis.coverage).toBe(0)
    expect(analysis.claimedAmountPaise).toBeNull()
  })
})

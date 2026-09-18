import { demoAnalysis } from './mockData'
import consistent from '../../synthetic/consistent.json'
import ambiguous from '../../synthetic/ambiguous.json'
import edge from '../../synthetic/legitimate-edge.json'
import type { Analysis, CheckStatus, EvidenceRef, Finding, UploadFile } from './types'

const storageKey = 'claimlens.synthetic.v2'
const names: Record<string, string> = {
  bill: 'itemized_bill.pdf',
  summary: 'discharge_summary.pdf',
  report: 'supporting_report.pdf',
}
const checks: Record<string, { names: string[]; title: string; detail: string }> = {
  'bill.total_reconciliation': {
    names: ['line_item_amount', 'invoice_total'],
    title: 'Invoice total reconciles',
    detail: 'The extracted line items and invoice total agree within the ₹1.00 tolerance.',
  },
  'packet.patient_identity': {
    names: ['patient_identifier'],
    title: 'Patient identifiers align',
    detail: 'The available bill and discharge summary carry the same member identifier.',
  },
  'packet.timeline': {
    names: ['admission_date', 'discharge_date', 'procedure_date'],
    title: 'Stay dates are consistent',
    detail: 'Available dates are consistent with the recorded stay and one-day allowance.',
  },
  'packet.supporting_evidence': {
    names: ['procedure_or_device_charge'],
    title: 'Supporting evidence needed',
    detail:
      'Request the supporting procedure or implant record. Its absence does not establish that care did not occur.',
  },
}

function fromPacket(
  packet: typeof ambiguous | typeof consistent | typeof edge,
  label: string,
  index: number,
): Analysis {
  const findings = Object.entries(packet.expected).map(([checkId, status]): Finding => {
    const check = checks[checkId]
    const evidence = packet.fields
      .filter((f) => check.names.includes(f.name))
      .map((f, i): EvidenceRef => ({
        evidenceId: 'ev_' + packet.packetId + '_' + f.blockId,
        documentId: f.documentId,
        documentName: names[f.documentId],
        documentVersion: 1,
        page: 1,
        blockIds: [f.blockId],
        geometry: { left: 0.1, top: 0.24 + i * 0.09, width: 0.8, height: 0.06 },
        confidence: label === 'Ambiguous amounts' ? 62 : 97,
        excerpt: f.name.replaceAll('_', ' ') + ': ' + f.value,
      }))
    const insufficient = status === 'INSUFFICIENT_EVIDENCE'
    return {
      id: packet.packetId + '_' + checkId,
      checkId,
      status: status as CheckStatus,
      priority: insufficient ? 'MEDIUM' : 'LOW',
      reviewerAction: 'OPEN',
      evidence,
      title: insufficient
        ? checkId === 'bill.total_reconciliation'
          ? 'Decimal separator needs confirmation'
          : checkId === 'packet.supporting_evidence'
            ? 'Supporting report is missing'
            : 'Not enough evidence to compare'
        : check.title,
      summary: insufficient
        ? checkId === 'bill.total_reconciliation'
          ? '“12,50” can mean different amounts under different number formats. Confirm the original before reconciling the bill.'
          : 'The packet does not contain enough reliable evidence for this check. No clean result has been inferred.'
        : check.detail,
      requestedEvidence: insufficient
        ? 'Provide or confirm the source document needed for this check.'
        : undefined,
    }
  })
  const documents = [...new Set(packet.fields.map((f) => f.documentId))].map((id) => ({
    id,
    name: names[id],
    version: 1,
    pages: 1,
    extractionQuality: label === 'Ambiguous amounts' ? 62 : 97,
    status: 'READY' as const,
    type: (id === 'bill'
      ? 'BILL'
      : id === 'summary'
        ? 'DISCHARGE_SUMMARY'
        : 'SUPPORTING_REPORT') as Analysis['documents'][number]['type'],
  }))
  const warnings = findings.some((f) => f.status === 'INSUFFICIENT_EVIDENCE')
  const claimed = packet.fields.find((f) => f.name === 'claimed_amount')?.normalizedValue
  return {
    id: packet.packetId,
    claimId: 'CLM-' + (20482 + index),
    scenario: label,
    status: warnings ? 'COMPLETED_WITH_WARNINGS' : 'COMPLETED',
    analysisVersion: 1,
    reviewPriority: warnings ? 'MEDIUM' : 'LOW',
    extractionQuality: label === 'Ambiguous amounts' ? 62 : 97,
    coverage: Math.round(
      (100 * findings.filter((f) => f.status === 'PASS').length) / findings.length,
    ),
    createdAt: new Date().toISOString(),
    claimedAmountPaise: typeof claimed === 'number' ? claimed : null,
    findings,
    documents,
    corrections: [],
    activity: [],
  }
}

function initial(): Analysis[] {
  return [
    structuredClone(demoAnalysis),
    fromPacket(consistent, 'Consistent packet', 0),
    fromPacket(ambiguous, 'Ambiguous amounts', 1),
    fromPacket(edge, 'Same-day stay', 2),
  ]
}
let records: Analysis[]
function load() {
  if (records) return records
  try {
    records = JSON.parse(sessionStorage.getItem(storageKey) || 'null') || initial()
  } catch {
    records = initial()
  }
  return records
}
function persist() {
  try {
    sessionStorage.setItem(storageKey, JSON.stringify(records))
  } catch {
    /* The demo remains usable with storage disabled. */
  }
}
export function demoList() {
  return structuredClone(load())
}
export function demoGet(id: string) {
  const record = load().find((item) => item.id === id)
  if (!record) throw new Error('Analysis not found. Open a packet from the review queue.')
  return structuredClone(record)
}
export function demoSave(record: Analysis) {
  const index = load().findIndex((item) => item.id === record.id)
  if (index < 0) records.unshift(structuredClone(record))
  else records[index] = structuredClone(record)
  persist()
}
export function demoUpdate(id: string, findingId: string, action: Finding['reviewerAction']) {
  const record = demoGet(id)
  const finding = record.findings.find((f) => f.id === findingId)
  if (!finding) throw new Error('Finding not found')
  finding.reviewerAction = action
  record.activity = [
    ...(record.activity || []),
    {
      id: crypto.randomUUID(),
      title: 'Marked ' + action?.toLowerCase(),
      detail: finding.title,
      at: new Date().toISOString(),
      actorId: 'demo-reviewer',
    },
  ]
  demoSave(record)
}
export function demoCorrect(id: string, fieldId: string, correctedValue: string) {
  const record = demoGet(id)
  if (!record.findings.some((f) => f.evidence.some((e) => e.evidenceId === fieldId)))
    throw new Error('Unknown evidence reference')
  const correction = {
    correctionId: crypto.randomUUID(),
    fieldId,
    correctedValue,
    createdAt: new Date().toISOString(),
    basedOnAnalysisVersion: record.analysisVersion,
    actorId: 'demo-reviewer',
  }
  record.corrections = [...(record.corrections || []), correction]
  record.activity = [
    ...(record.activity || []),
    {
      id: correction.correctionId,
      title: 'Extraction correction recorded',
      detail: 'Original source preserved. Automated checks have not been rerun.',
      at: correction.createdAt,
      actorId: 'demo-reviewer',
    },
  ]
  demoSave(record)
  return correction
}
export function demoUpload(files: UploadFile[], key: string) {
  const id = 'local_' + key
  if (load().some((a) => a.id === id)) return { analysisId: id, status: demoGet(id).status }
  // No uploaded bytes are read, stored, or represented as OCR results in mock mode.
  const record: Analysis = {
    id,
    claimId: 'LOCAL-' + (load().length + 1),
    scenario: 'Local upload',
    analysisVersion: 1,
    status: 'COMPLETED_WITH_WARNINGS',
    reviewPriority: 'MEDIUM',
    extractionQuality: 0,
    coverage: 0,
    createdAt: new Date().toISOString(),
    claimedAmountPaise: null,
    documents: files.map((item, i) => ({
      id: id + '_' + i,
      name: item.file.name,
      type: item.type,
      version: 1,
      pages: 0,
      extractionQuality: null,
      status: 'FAILED',
    })),
    findings: [
      {
        id: id + '_extraction',
        checkId: 'extraction.unavailable',
        title: 'Cloud extraction is unavailable in mock mode',
        summary:
          'Your files were not processed or uploaded. Use a sample packet to explore the review workflow, or configure AWS to extract and analyze these documents.',
        status: 'ERROR',
        priority: 'MEDIUM',
        evidence: [],
        reviewerAction: 'OPEN',
      },
    ],
    corrections: [],
    activity: [],
  }
  demoSave(record)
  return { analysisId: id, status: record.status }
}

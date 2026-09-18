export type CheckStatus = 'PASS' | 'FINDING' | 'INSUFFICIENT_EVIDENCE' | 'NOT_APPLICABLE' | 'ERROR'
export type ReviewPriority = 'LOW' | 'MEDIUM' | 'HIGH'

export interface Geometry {
  left: number
  top: number
  width: number
  height: number
}
export interface EvidenceRef {
  evidenceId: string
  documentId: string
  documentName: string
  page: number
  blockIds: string[]
  geometry: Geometry
  confidence: number
  excerpt: string
  documentVersion?: number
}
export interface Finding {
  id: string
  checkId: string
  title: string
  summary: string
  status: CheckStatus
  priority: ReviewPriority
  evidence: EvidenceRef[]
  requestedEvidence?: string
  reviewerAction?: 'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED'
}
export interface DocumentRecord {
  id: string
  name: string
  type: 'BILL' | 'DISCHARGE_SUMMARY' | 'SUPPORTING_REPORT'
  version: number
  pages: number
  extractionQuality: number | null
  status: 'READY' | 'PARTIAL' | 'EXTRACTING' | 'FAILED' | 'AWAITING_UPLOAD'
}
export interface Analysis {
  id: string
  claimId: string
  status: 'QUEUED' | 'PROCESSING' | 'COMPLETED' | 'COMPLETED_WITH_WARNINGS' | 'FAILED'
  analysisVersion: number
  reviewPriority: ReviewPriority
  extractionQuality: number
  coverage: number
  createdAt: string
  claimedAmountPaise: number | null
  findings: Finding[]
  documents: DocumentRecord[]
  corrections?: Correction[]
  activity?: Activity[]
  scenario?: string
}

export interface Correction {
  correctionId: string
  fieldId: string
  correctedValue: string
  createdAt: string
  basedOnAnalysisVersion?: number
  actorId?: string
}
export interface Activity {
  id: string
  title: string
  detail: string
  at: string
  actorId?: string
}
export interface UploadFile {
  file: File
  type: DocumentRecord['type']
}
export interface UploadProgress {
  step: string
  completed: number
  total: number
}

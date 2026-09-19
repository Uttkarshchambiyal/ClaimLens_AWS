import { demoCorrect, demoGet, demoList, demoUpdate, demoUpload } from './demoStore'
import { appMode, isValidAppMode } from './appConfig'
import { requireUser } from './auth'
import type { Analysis, Finding, UploadFile, UploadProgress } from './types'

export { appMode } from './appConfig'
const apiBase = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '')

async function request<T>(
  path: string,
  token?: string,
  method = 'GET',
  body?: unknown,
  key?: string,
): Promise<T> {
  if (!isValidAppMode)
    throw new Error('Invalid application mode. Set VITE_APP_MODE to mock or production.')
  if (!apiBase)
    throw new Error(
      'AWS API is not configured. Set VITE_API_BASE_URL and Cognito settings, or explicitly select mock mode.',
    )
  // Obtain the current ID token after silent renewal, not a stale render snapshot.
  token = (await requireUser())?.id_token || token
  if (!token) throw new Error('Your session has expired. Sign in again to continue.')
  const response = await fetch(apiBase + path, {
    method,
    signal: AbortSignal.timeout(30000),
    headers: {
      Authorization: 'Bearer ' + token,
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...(key ? { 'Idempotency-Key': key } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!response.ok) {
    const error = await response.json().catch(() => null)
    throw new Error(
      response.status === 401
        ? 'Your session has expired. Sign in again.'
        : response.status === 403
          ? 'You do not have access to this record.'
          : error?.message || 'Request failed (' + response.status + '). Please retry.',
    )
  }
  return response.json()
}
export async function listAnalyses(token?: string): Promise<Analysis[]> {
  if (appMode === 'mock') return demoList()
  return (await request<{ analyses: Analysis[] }>('/analyses', token)).analyses
}
export async function getAnalysis(id: string, token?: string): Promise<Analysis> {
  if (appMode === 'mock') return demoGet(id)
  return request('/analyses/' + encodeURIComponent(id), token)
}
export async function updateFinding(
  id: string,
  findingId: string,
  action: Finding['reviewerAction'],
  token?: string,
) {
  if (appMode === 'mock') return demoUpdate(id, findingId, action)
  return request(
    '/analyses/' + encodeURIComponent(id) + '/findings/' + encodeURIComponent(findingId),
    token,
    'PATCH',
    { reviewerAction: action },
    crypto.randomUUID(),
  )
}
export function validateUploads(files: UploadFile[]): string | null {
  if (!files.length) return 'Add at least one itemized bill.'
  if (files.length > 10) return 'A packet can contain up to 10 documents.'
  if (files.filter((item) => item.type === 'BILL').length !== 1)
    return 'Assign exactly one itemized bill per packet.'
  for (const { file } of files) {
    if (!['application/pdf', 'image/png', 'image/jpeg'].includes(file.type))
      return file.name + ': use a PDF, PNG, or JPEG file.'
    if (!file.size || file.size > 15 * 1024 * 1024)
      return file.name + ': files must be nonempty and no larger than 15 MB.'
  }
  return null
}
export async function createAnalysis(
  files: UploadFile[],
  token: string | undefined,
  key: string,
  onProgress: (progress: UploadProgress) => void,
) {
  const invalid = validateUploads(files)
  if (invalid) throw new Error(invalid)
  if (appMode === 'mock') return demoUpload(files, key)
  onProgress({ step: 'Creating claim', completed: 0, total: files.length + 2 })
  const claim = await request<{ claimId: string }>('/claims', token, 'POST', {}, key)
  const documentIds: string[] = []
  for (const [index, { file, type }] of files.entries()) {
    onProgress({ step: 'Uploading ' + file.name, completed: index + 1, total: files.length + 2 })
    const upload = await request<{
      documentId: string
      uploadUrl: string
      uploadFields: Record<string, string>
      method: 'POST'
    }>(
      '/claims/' + claim.claimId + '/documents/upload-request',
      token,
      'POST',
      { filename: file.name, contentType: file.type, documentType: type, sizeBytes: file.size },
      key + '-file-' + index,
    )
    const form = new FormData()
    Object.entries(upload.uploadFields).forEach(([name, value]) => form.append(name, value))
    form.append('file', file)
    const response = await fetch(upload.uploadUrl, {
      method: upload.method,
      body: form,
      signal: AbortSignal.timeout(120000),
    })
    if (!response.ok)
      throw new Error('Upload failed for ' + file.name + '. Retry to resume this packet.')
    documentIds.push(upload.documentId)
  }
  onProgress({ step: 'Starting analysis', completed: files.length + 1, total: files.length + 2 })
  return request<{ analysisId: string; status: string }>(
    '/analyses',
    token,
    'POST',
    { claimId: claim.claimId, documentIds },
    key + '-analysis',
  )
}
export async function correctExtraction(
  id: string,
  fieldId: string,
  correctedValue: string,
  token?: string,
) {
  if (appMode === 'mock') return demoCorrect(id, fieldId, correctedValue)
  return request(
    '/analyses/' + encodeURIComponent(id) + '/corrections',
    token,
    'PATCH',
    { fieldId, correctedValue },
    crypto.randomUUID(),
  )
}
export async function getReport(id: string, token?: string) {
  if (appMode === 'mock') {
    const analysis = demoGet(id)
    return {
      mode: 'MOCK — synthetic data',
      reportVersion: analysis.analysisVersion,
      generatedAt: new Date().toISOString(),
      analysis,
      disclaimer: 'Human review required. This report does not adjudicate the claim.',
    }
  }
  return request('/analyses/' + encodeURIComponent(id) + '/report', token)
}
export async function getDocumentSource(
  claimId: string,
  documentId: string,
  token?: string,
): Promise<{ downloadUrl: string; contentType: string }> {
  return request(
    '/claims/' + encodeURIComponent(claimId) + '/documents/' + encodeURIComponent(documentId),
    token,
  )
}

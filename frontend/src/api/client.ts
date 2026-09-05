import type {
  Decision,
  Document,
  DocType,
  Health,
  ModelsInfo,
  Review,
} from '../types'

const BASE = '/api'

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init)
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(text || `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

function json(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }
}

export const api = {
  health: () => req<Health>('/health'),
  models: () => req<ModelsInfo>('/models'),

  documents: () => req<Document[]>('/documents'),
  rescan: () => req<{ enqueued: number }>('/documents/rescan', { method: 'POST' }),
  reindexAll: () => req<{ started: boolean }>('/documents/reindex', { method: 'POST' }),
  uploadDocument: (file: File, docType: DocType, mode?: string, password?: string) => {
    const form = new FormData()
    form.append('file', file)
    form.append('doc_type', docType)
    if (mode) form.append('mode', mode)
    if (password) form.append('password', password)
    return req<Document>('/documents', { method: 'POST', body: form })
  },
  unlockDocument: (id: string, password: string) =>
    req<Document>(`/documents/${id}/unlock`, json('POST', { password })),
  runOcr: (id: string, password?: string) =>
    req<Document>(`/documents/${id}/ocr`, json('POST', { password })),
  deleteDocument: (id: string) =>
    req<{ deleted: string }>(`/documents/${id}`, { method: 'DELETE' }),

  reviews: () => req<Review[]>('/reviews'),
  review: (id: string) => req<Review>(`/reviews/${id}`),
  deleteReview: (id: string) =>
    req<{ deleted: string }>(`/reviews/${id}`, { method: 'DELETE' }),
  createReview: (
    frd: File,
    nfrd: File,
    frdPassword?: string,
    nfrdPassword?: string,
    exposure?: string,
    changeScope?: string,
  ) => {
    const form = new FormData()
    form.append('frd', frd)
    form.append('nfrd', nfrd)
    if (frdPassword) form.append('frd_password', frdPassword)
    if (nfrdPassword) form.append('nfrd_password', nfrdPassword)
    if (exposure && exposure !== 'auto') form.append('exposure', exposure)
    if (changeScope && changeScope !== 'auto') form.append('change_scope', changeScope)
    return req<Review>('/reviews', { method: 'POST', body: form })
  },
  updateExposure: (id: string, exposure: string | null) =>
    req<Review>(`/reviews/${id}/exposure`, json('PATCH', { exposure })),
  updateChangeScope: (id: string, changeScope: string | null) =>
    req<Review>(`/reviews/${id}/change-scope`, json('PATCH', { change_scope: changeScope })),
  setDecision: (id: string, decision: Decision) =>
    req<Review>(`/reviews/${id}/decision`, json('PATCH', decision)),
}

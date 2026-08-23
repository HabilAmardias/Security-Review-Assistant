import type { Document } from '../types'
import { api } from '../api/client'
import { usePolling } from './usePolling'

const ACTIVE: Document['status'][] = ['pending', 'extracting', 'chunking', 'embedding']

export function useDocuments() {
  const { data, error, loading } = usePolling<Document[]>(() => api.documents(), 4000, [])
  const docs = data ?? []
  const hasActive = docs.some((d) => ACTIVE.includes(d.status))
  return { docs, error, loading, hasActive }
}

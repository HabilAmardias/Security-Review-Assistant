import type { Review } from '../types'
import { api } from '../api/client'
import { usePolling } from './usePolling'

export function useReviews() {
  const { data, error, loading } = usePolling<Review[]>(() => api.reviews(), 4000, [])
  return { reviews: data ?? [], error, loading }
}

export function useReview(id: string | undefined) {
  const { data, error, loading } = usePolling<Review>(
    () => (id ? api.review(id) : Promise.reject(new Error('no id'))),
    3000,
    [id],
  )
  return { review: data ?? null, error, loading }
}

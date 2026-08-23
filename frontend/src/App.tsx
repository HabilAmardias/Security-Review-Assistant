import { Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { KnowledgeBase } from './pages/KnowledgeBase'
import { NewReview } from './pages/NewReview'
import { ReviewDetail } from './pages/ReviewDetail'
import { ReviewHistory } from './pages/ReviewHistory'
import { Settings } from './pages/Settings'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<KnowledgeBase />} />
        <Route path="new-review" element={<NewReview />} />
        <Route path="reviews" element={<ReviewHistory />} />
        <Route path="reviews/:id" element={<ReviewDetail />} />
        <Route path="settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}

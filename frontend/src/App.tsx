import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from '@/components/common/Layout'
import { HomePage } from '@/pages/HomePage'
import { ReadingPage } from '@/pages/ReadingPage'
import { PassageDetailPage } from '@/pages/PassageDetailPage'
import { VocabularyPage } from '@/pages/VocabularyPage'
import { ImportPage } from '@/pages/ImportPage'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<HomePage />} />
          <Route path="import" element={<ImportPage />} />
          <Route path="reading" element={<ReadingPage />} />
          <Route path="reading/:id" element={<PassageDetailPage />} />
          <Route path="vocabulary" element={<VocabularyPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App

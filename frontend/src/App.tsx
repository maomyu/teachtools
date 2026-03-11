import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from '@/components/common/Layout'
import { HomePage } from '@/pages/HomePage'
import { ReadingContent } from '@/pages/ReadingContent'
import { PassageDetailPage } from '@/pages/PassageDetailPage'
import { ImportPage } from '@/pages/ImportPage'
import { VocabularyPage } from '@/pages/VocabularyPage'
import { ClozePage } from '@/pages/ClozePage'
import { HandoutView } from '@/components/handout/HandoutView'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<HomePage />} />
          <Route path="import" element={<ImportPage />} />
          <Route path="reading" element={<ReadingContent />} />
          <Route path="reading/:id" element={<PassageDetailPage />} />
          <Route path="vocabulary" element={<VocabularyPage />} />
          <Route path="cloze" element={<ClozePage />} />
          <Route path="handout" element={<HandoutView />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App

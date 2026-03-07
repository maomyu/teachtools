import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from '@/components/common/Layout'
import { HomePage } from '@/pages/HomePage'
import { ReadingTabsPage } from '@/pages/ReadingTabsPage'
import { PassageDetailPage } from '@/pages/PassageDetailPage'
import { ImportPage } from '@/pages/ImportPage'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<HomePage />} />
          <Route path="import" element={<ImportPage />} />
          <Route path="reading" element={<ReadingTabsPage />} />
          <Route path="reading/:id" element={<PassageDetailPage />} />
          <Route path="vocabulary" element={<Navigate to="/reading" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App

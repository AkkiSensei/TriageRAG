import type { FC } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClient } from '@/lib/api'
import { Layout } from '@/components/layout/Layout'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { TriageProvider } from '@/context/TriageContext'
import { IntakePage } from '@/pages/IntakePage'
import { ReportPage } from '@/pages/ReportPage'

export const App: FC = () => {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <TriageProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<Layout />}>
                <Route index element={<Navigate to="/intake" replace />} />
                <Route path="intake" element={<IntakePage />} />
                <Route path="report" element={<ReportPage />} />
                <Route path="*" element={<Navigate to="/intake" replace />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </TriageProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  )
}

export default App

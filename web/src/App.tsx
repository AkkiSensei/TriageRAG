import type { FC } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClient } from '@/lib/api'
import { Layout } from '@/components/layout/Layout'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { ThemeProvider } from '@/context/ThemeContext'
import { TriageProvider } from '@/context/TriageContext'
import { IntakePage } from '@/pages/IntakePage'
import { ReportPage } from '@/pages/ReportPage'
import { RedTeamPage } from '@/pages/RedTeamPage'
import { RulesPage } from '@/pages/RulesPage'
import { ProtocolsPage } from '@/pages/ProtocolsPage'
import { EvidencePage } from '@/pages/EvidencePage'
import { AuditPage } from '@/pages/AuditPage'

export const App: FC = () => {
  return (
    <ErrorBoundary>
      <ThemeProvider>
        <QueryClientProvider client={queryClient}>
          <TriageProvider>
            <BrowserRouter>
              <Routes>
                <Route path="/" element={<Layout />}>
                  <Route index element={<Navigate to="/intake" replace />} />
                  <Route path="intake" element={<IntakePage />} />
                  <Route path="report" element={<ReportPage />} />
                  <Route path="redteam" element={<RedTeamPage />} />
                  <Route path="rules" element={<RulesPage />} />
                  <Route path="protocols" element={<ProtocolsPage />} />
                  <Route path="evidence" element={<EvidencePage />} />
                  <Route path="audit" element={<AuditPage />} />
                  <Route path="*" element={<Navigate to="/intake" replace />} />
                </Route>
              </Routes>
            </BrowserRouter>
          </TriageProvider>
        </QueryClientProvider>
      </ThemeProvider>
    </ErrorBoundary>
  )
}

export default App

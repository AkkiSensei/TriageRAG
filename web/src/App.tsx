import type { FC } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClient } from '@/lib/api'
import { MotionProvider } from '@/lib/motion'
import { Layout } from '@/components/layout/Layout'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { ConsolePage } from '@/pages/ConsolePage'
import { RedTeamPage } from '@/pages/RedTeamPage'
import { ClinicalIntelligencePage } from '@/pages/ClinicalIntelligencePage'
import { AboutPage } from '@/pages/AboutPage'

export const App: FC = () => {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <MotionProvider>
          <BrowserRouter>
            <Routes>
            <Route path="/" element={<Layout />}>
              <Route index element={<ConsolePage />} />
              <Route path="console" element={<Navigate to="/" replace />} />
              <Route path="redteam" element={<RedTeamPage />} />
              <Route path="intelligence" element={<ClinicalIntelligencePage />} />
              <Route path="ruleset" element={<ClinicalIntelligencePage initialTab="rules" />} />
              <Route path="protocols" element={<ClinicalIntelligencePage initialTab="protocols" />} />
              <Route path="evidence" element={<ClinicalIntelligencePage initialTab="evidence" />} />
              <Route path="audit" element={<ClinicalIntelligencePage initialTab="audit" />} />
              <Route path="about" element={<AboutPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </MotionProvider>
    </QueryClientProvider>
    </ErrorBoundary>
  )
}

export default App

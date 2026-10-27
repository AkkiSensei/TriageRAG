import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClient } from '@/lib/api'
import { MotionProvider } from '@/lib/motion'
import { Layout } from '@/components/layout/Layout'
import { ConsolePage } from '@/pages/ConsolePage'
import { RedTeamPage } from '@/pages/RedTeamPage'
import { RulesetPage } from '@/pages/RulesetPage'
import { ProtocolsPage } from '@/pages/ProtocolsPage'
import { EvidencePage } from '@/pages/EvidencePage'
import { AuditPage } from '@/pages/AuditPage'
import { AboutPage } from '@/pages/AboutPage'

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <MotionProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Layout />}>
              <Route index element={<ConsolePage />} />
              <Route path="console" element={<Navigate to="/" replace />} />
              <Route path="redteam" element={<RedTeamPage />} />
              <Route path="ruleset" element={<RulesetPage />} />
              <Route path="protocols" element={<ProtocolsPage />} />
              <Route path="evidence" element={<EvidencePage />} />
              <Route path="audit" element={<AuditPage />} />
              <Route path="about" element={<AboutPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </MotionProvider>
    </QueryClientProvider>
  )
}

export default App

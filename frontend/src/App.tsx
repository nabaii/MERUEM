import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { Toaster } from 'react-hot-toast'

import { AppShell } from './components/layout/AppShell'
import { LoginPage } from './pages/LoginPage'
import { RegisterPage } from './pages/RegisterPage'
import { DashboardPage } from './pages/DashboardPage'
import { AudienceExplorerPage } from './pages/AudienceExplorerPage'
import { ProfileDetailPage } from './pages/ProfileDetailPage'
import { ClustersPage } from './pages/ClustersPage'
import { ClusterDetailPage } from './pages/ClusterDetailPage'
import { SettingsPage } from './pages/SettingsPage'
import { CampaignsPage } from './pages/CampaignsPage'
import { CampaignDetailPage } from './pages/CampaignDetailPage'
import { CampaignBuilderPage } from './pages/CampaignBuilderPage'
import { ImportPage } from './pages/ImportPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 60_000,
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          {/* Public */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          {/* Protected */}
          <Route element={<AppShell />}>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/explorer" element={<AudienceExplorerPage />} />
            <Route path="/profiles/:id" element={<ProfileDetailPage />} />
            <Route path="/clusters" element={<ClustersPage />} />
            <Route path="/clusters/:id" element={<ClusterDetailPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            {/* Phase 5 — campaigns */}
            <Route path="/campaigns" element={<CampaignsPage />} />
            <Route path="/campaigns/new" element={<CampaignBuilderPage />} />
            <Route path="/campaigns/:id" element={<CampaignDetailPage />} />
            {/* Phase 7 — multi-source data import */}
            <Route path="/import" element={<ImportPage />} />
          </Route>

          {/* Default redirect */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>

      <Toaster
        position="bottom-right"
        toastOptions={{
          style: {
            background: '#1e293b',
            color: '#f1f5f9',
            border: '1px solid #334155',
            borderRadius: '10px',
            fontSize: '14px',
          },
        }}
      />

      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  )
}

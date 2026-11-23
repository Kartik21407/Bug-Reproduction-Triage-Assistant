// Route table: maps every path to a page. Public pages are the landing page
// and the two sign-in screens; everything else sits inside ProtectedRoute,
// which also draws the signed-in shell, and the admin page inside
// AdminRoute as well.

import { Navigate, Route, Routes } from 'react-router-dom';
import Welcome from '@/pages/Welcome';
import Login from '@/pages/Login';
import Register from '@/pages/Register';
import Dashboard from '@/pages/Dashboard';
import NewReport from '@/pages/NewReport';
import History from '@/pages/History';
import ReportDetail from '@/pages/ReportDetail';
import MaskingReview from '@/pages/MaskingReview';
import AnalysisReview from '@/pages/AnalysisReview';
import TriageReview from '@/pages/TriageReview';
import GeneratedReport from '@/pages/GeneratedReport';
import GitHubIssue from '@/pages/GitHubIssue';
import GitHubSettings from '@/pages/GitHubSettings';
import Analytics from '@/pages/Analytics';
import Admin from '@/pages/Admin';
import { AdminRoute, ProtectedRoute } from '@/components/layout/ProtectedRoute';

export function AppRouter() {
  return (
    <Routes>
      <Route path="/welcome" element={<Welcome />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/reports/new" element={<NewReport />} />
        <Route path="/reports" element={<History />} />
        <Route path="/reports/:id" element={<ReportDetail />} />
        <Route path="/reports/:id/mask" element={<MaskingReview />} />
        <Route path="/reports/:id/analysis" element={<AnalysisReview />} />
        <Route path="/reports/:id/triage" element={<TriageReview />} />
        <Route path="/reports/:id/report" element={<GeneratedReport />} />
        <Route path="/reports/:id/github" element={<GitHubIssue />} />
        <Route path="/settings/github" element={<GitHubSettings />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route element={<AdminRoute />}>
          <Route path="/admin" element={<Admin />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/welcome" replace />} />
    </Routes>
  );
}

// Route table: maps every path to a page, and guards the private ones with
// ProtectedRoute. Routes are added here as their story builds the page, so
// this file only ever references pages that actually exist.

import { Link, Navigate, Route, Routes } from 'react-router-dom';
import Login from '@/pages/Login';
import Register from '@/pages/Register';
import NewReport from '@/pages/NewReport';
import History from '@/pages/History';
import ReportDetail from '@/pages/ReportDetail';
import { ProtectedRoute } from '@/components/layout/ProtectedRoute';
import { useLogout } from '@/hooks/useAuth';

// Temporary landing element for "/". Replaced once Dashboard.tsx is built;
// Dashboard is not required by any Sprint 1 story, so it stays a stub until
// something needs it.
function SignedInPlaceholder() {
  const logout = useLogout();
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-6 text-center">
      <p className="text-sm text-muted-foreground">
        Signed in. The dashboard is built in a later story.
      </p>
      <div className="flex gap-4">
        <Link to="/reports/new" className="text-sm font-medium underline">
          Submit a report
        </Link>
        <Link to="/reports" className="text-sm font-medium underline">
          History
        </Link>
      </div>
      <button
        type="button"
        onClick={() => logout.mutate()}
        className="rounded-md border px-3 py-2 text-sm font-medium"
      >
        Sign out
      </button>
    </div>
  );
}

export function AppRouter() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/" element={<SignedInPlaceholder />} />
        <Route path="/reports/new" element={<NewReport />} />
        <Route path="/reports" element={<History />} />
        <Route path="/reports/:id" element={<ReportDetail />} />
      </Route>
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}

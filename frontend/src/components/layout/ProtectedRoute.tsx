// Route guard: renders the child route when a session exists, otherwise
// redirects to Login. This is the one component in components/ allowed to
// read session state directly, since guarding is its whole job.

import { Navigate, Outlet } from 'react-router-dom';
import { useCurrentUser } from '@/hooks/useAuth';
import { LoadingState } from '@/components/states';

export function ProtectedRoute() {
  const { data: user, isLoading } = useCurrentUser();

  if (isLoading) {
    return <LoadingState label="Checking your session…" />;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}

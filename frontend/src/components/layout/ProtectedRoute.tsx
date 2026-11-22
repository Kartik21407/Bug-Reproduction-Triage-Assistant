// Route guards. ProtectedRoute renders the signed-in shell (sidebar, top
// bar) around the child route when a session exists; otherwise it sends
// the visitor to the landing page from "/" and to Login from anywhere else.
// AdminRoute additionally requires the administrator role (US-03
// criterion 3); the server enforces the same rule. These are the
// components in components/ allowed to read session state directly, since
// guarding is their whole job.

import { Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useCurrentUser, useLogout } from '@/hooks/useAuth';
import { LoadingState } from '@/components/states';
import { MobileNav, Sidebar } from '@/components/layout/Sidebar';
import { TopBar } from '@/components/layout/TopBar';

export function ProtectedRoute() {
  const { data: user, isLoading } = useCurrentUser();
  const logout = useLogout();
  const location = useLocation();
  const navigate = useNavigate();

  if (isLoading) {
    return <LoadingState label="Checking your session…" />;
  }

  if (!user) {
    return <Navigate to={location.pathname === '/' ? '/welcome' : '/login'} replace />;
  }

  const signOut = () => logout.mutate(undefined, { onSuccess: () => navigate('/welcome') });

  return (
    <div className="flex min-h-screen">
      <Sidebar isAdmin={user.is_admin} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar
          email={user.email}
          isAdmin={user.is_admin}
          isSigningOut={logout.isPending}
          onSignOut={signOut}
        />
        <MobileNav isAdmin={user.is_admin} />
        <main className="flex-1">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export function AdminRoute() {
  const { data: user } = useCurrentUser();
  if (!user?.is_admin) {
    return <Navigate to="/" replace />;
  }
  return <Outlet />;
}

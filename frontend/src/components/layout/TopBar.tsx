// The page header: the signed-in user, an Administrator badge for
// administrators, and the sign-out action.

import { LogOut } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Logo } from '@/components/layout/Logo';

interface TopBarProps {
  email: string;
  isAdmin: boolean;
  isSigningOut: boolean;
  onSignOut: () => void;
}

export function TopBar({ email, isAdmin, isSigningOut, onSignOut }: TopBarProps) {
  return (
    <header className="flex items-center justify-between gap-4 border-b border-border/70 bg-card/60 px-4 py-3 backdrop-blur sm:px-6">
      <div className="md:hidden">
        <Logo size="sm" />
      </div>
      <Link
        to="/reports/new"
        className="hidden text-sm text-muted-foreground hover:text-primary md:block"
      >
        Spotted a bug? <span className="font-medium text-primary">File a new report</span>
      </Link>
      <div className="flex items-center gap-3">
        <div className="hidden flex-col items-end sm:flex">
          <span className="text-sm font-medium">{email}</span>
          {isAdmin && (
            <span className="text-[11px] font-semibold uppercase tracking-wide text-primary">
              Administrator
            </span>
          )}
        </div>
        <span
          aria-hidden="true"
          className="flex h-9 w-9 items-center justify-center rounded-full bg-accent text-sm font-semibold uppercase text-accent-foreground"
        >
          {email.charAt(0)}
        </span>
        <button
          type="button"
          onClick={onSignOut}
          disabled={isSigningOut}
          className="btn-secondary px-3 py-1.5"
        >
          <LogOut className="h-4 w-4" aria-hidden="true" />
          Sign out
        </button>
      </div>
    </header>
  );
}

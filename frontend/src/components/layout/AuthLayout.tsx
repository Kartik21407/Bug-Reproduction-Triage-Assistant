// The frame around Sign in and Sign up: the logo and "Back to home" at the
// top, and one centred card with a heading, a Sign in / Sign up switch and
// the form.

import { ArrowLeft } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Logo } from '@/components/layout/Logo';

interface AuthLayoutProps {
  title: string;
  subtitle: string;
  active: 'signin' | 'signup';
  children: React.ReactNode;
}

const TABS = [
  { key: 'signin', label: 'Sign in', to: '/login' },
  { key: 'signup', label: 'Sign up', to: '/register' },
] as const;

export function AuthLayout({ title, subtitle, active, children }: AuthLayoutProps) {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex items-center justify-between px-6 py-5">
        <Logo to="/welcome" />
        <Link
          to="/welcome"
          className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-primary"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Back to home
        </Link>
      </header>
      <main className="flex flex-1 items-start justify-center px-4 pb-12 pt-6 sm:pt-12">
        <div className="card w-full max-w-md p-8 shadow-lift">
          <div className="mb-6 text-center">
            <h1 className="text-2xl font-bold">{title}</h1>
            <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
          </div>
          <nav
            aria-label="Sign in or sign up"
            className="mb-6 grid grid-cols-2 rounded-xl bg-muted p-1"
          >
            {TABS.map((tab) => (
              <Link
                key={tab.key}
                to={tab.to}
                aria-current={active === tab.key ? 'page' : undefined}
                className={`rounded-lg py-2 text-center text-sm font-medium transition ${
                  active === tab.key
                    ? 'bg-white text-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                {tab.label}
              </Link>
            ))}
          </nav>
          {children}
        </div>
      </main>
    </div>
  );
}

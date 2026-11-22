// Primary navigation between the signed-in sections. The Admin entry is
// shown only to administrators (US-03 criterion 3); the server refuses
// everyone else regardless.

import {
  BarChart3,
  FilePlus2,
  GitBranch,
  History,
  LayoutDashboard,
  ShieldCheck,
  type LucideIcon,
} from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { Logo } from '@/components/layout/Logo';

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
}

const ITEMS: NavItem[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/reports/new', label: 'New report', icon: FilePlus2, end: true },
  { to: '/reports', label: 'History', icon: History, end: true },
  { to: '/analytics', label: 'Analytics', icon: BarChart3 },
  { to: '/settings/github', label: 'GitHub', icon: GitBranch },
];

const ADMIN_ITEM: NavItem = { to: '/admin', label: 'Admin', icon: ShieldCheck };

function linkClass({ isActive }: { isActive: boolean }): string {
  return `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
    isActive
      ? 'bg-accent text-accent-foreground'
      : 'text-muted-foreground hover:bg-muted hover:text-foreground'
  }`;
}

export function Sidebar({ isAdmin }: { isAdmin: boolean }) {
  const items = isAdmin ? [...ITEMS, ADMIN_ITEM] : ITEMS;
  return (
    <aside className="hidden w-60 shrink-0 flex-col gap-8 border-r border-border/70 bg-card/60 px-4 py-6 backdrop-blur md:flex">
      <div className="px-2">
        <Logo size="sm" />
      </div>
      <nav aria-label="Main" className="flex flex-col gap-1">
        {items.map(({ to, label, icon: Icon, end }) => (
          <NavLink key={to} to={to} end={end} className={linkClass}>
            <Icon className="h-4 w-4" aria-hidden="true" />
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}

// The same links as a scrolling row, for narrow screens where the sidebar
// is hidden.
export function MobileNav({ isAdmin }: { isAdmin: boolean }) {
  const items = isAdmin ? [...ITEMS, ADMIN_ITEM] : ITEMS;
  return (
    <nav
      aria-label="Main"
      className="flex gap-1 overflow-x-auto border-b border-border/70 bg-card/60 px-3 py-2 md:hidden"
    >
      {items.map(({ to, label, icon: Icon, end }) => (
        <NavLink key={to} to={to} end={end} className={linkClass}>
          <Icon className="h-4 w-4" aria-hidden="true" />
          <span className="whitespace-nowrap">{label}</span>
        </NavLink>
      ))}
    </nav>
  );
}

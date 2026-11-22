// The BugTriage mark: a shield in a rounded orange square, and the name
// with "Triage" in the accent colour.

import { ShieldCheck } from 'lucide-react';
import { Link } from 'react-router-dom';

interface LogoProps {
  to?: string;
  size?: 'sm' | 'md';
  beta?: boolean;
}

export function Logo({ to = '/', size = 'md', beta = false }: LogoProps) {
  const box = size === 'md' ? 'h-10 w-10' : 'h-8 w-8';
  const icon = size === 'md' ? 'h-5 w-5' : 'h-4 w-4';
  const text = size === 'md' ? 'text-xl' : 'text-lg';
  return (
    <Link to={to} className="flex items-center gap-2.5" aria-label="BugTriage home">
      <span
        className={`flex ${box} items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm`}
      >
        <ShieldCheck className={icon} aria-hidden="true" />
      </span>
      <span className={`${text} font-bold tracking-tight`}>
        Bug<span className="text-primary">Triage</span>
      </span>
      {beta && (
        <span className="rounded-md bg-accent px-2 py-0.5 text-[10px] font-semibold tracking-widest text-accent-foreground">
          BETA
        </span>
      )}
    </Link>
  );
}

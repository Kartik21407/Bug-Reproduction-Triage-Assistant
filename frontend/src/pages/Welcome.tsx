// The public landing page at /welcome: what the product does, and the way
// in to sign up or sign in. A signed-in visitor is offered their dashboard
// instead.

import {
  ArrowRight,
  Bug,
  FileText,
  Heart,
  Layers,
  Search,
  Target,
  Zap,
  type LucideIcon,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { Logo } from '@/components/layout/Logo';
import { useCurrentUser } from '@/hooks/useAuth';

const FEATURES: { icon: LucideIcon; tint: string; title: string; text: string }[] = [
  {
    icon: Bug,
    tint: 'bg-accent text-primary',
    title: 'Smart Triage',
    text: 'Auto-classify severity, priority and category with rule-based reasoning and AI analysis.',
  },
  {
    icon: Search,
    tint: 'bg-blue-50 text-blue-600',
    title: 'Duplicate Detection',
    text: 'Sentence-level embeddings find near-duplicate issues across your corpus in milliseconds.',
  },
  {
    icon: FileText,
    tint: 'bg-emerald-50 text-emerald-600',
    title: 'Generated Reports',
    text: 'One-click Markdown reports with environment, reproduction steps, and masking built in.',
  },
];

const CHIPS: { icon: LucideIcon; text: string }[] = [
  { icon: Zap, text: 'AI-powered analysis' },
  { icon: Target, text: 'Severity prediction' },
  { icon: Layers, text: 'Actionable feedback report' },
];

const STEPS = ['Submit', 'Review', 'Triage', 'Export'];

export default function Welcome() {
  const { data: user } = useCurrentUser();

  return (
    <div className="flex min-h-screen flex-col">
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-6">
        <Logo to="/welcome" beta />
        <nav className="flex items-center gap-3">
          {user ? (
            <Link to="/" className="btn-primary">
              Open dashboard <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Link>
          ) : (
            <>
              <Link to="/login" className="px-3 py-2 text-sm font-medium hover:text-primary">
                Sign in
              </Link>
              <Link to="/register" className="btn-primary">
                Sign up <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Link>
            </>
          )}
        </nav>
      </header>

      <main className="flex-1">
        <section className="mx-auto grid w-full max-w-6xl items-center gap-12 px-6 py-12 lg:grid-cols-2 lg:py-20">
          <div className="flex flex-col gap-7">
            <h1 className="text-5xl font-extrabold leading-[1.05] sm:text-6xl">
              File better bugs, <em className="font-extrabold text-primary">triaged</em> before they
              land.
            </h1>
            <p className="max-w-xl text-lg leading-relaxed text-muted-foreground">
              Turn raw observations into structured, actionable bug reports. Automatic severity
              prediction, duplicate detection and a clean report, all in one flow.
            </p>
            <ul className="flex flex-wrap gap-2.5">
              {CHIPS.map(({ icon: Icon, text }) => (
                <li
                  key={text}
                  className="flex items-center gap-2 rounded-full border bg-card px-3.5 py-1.5 text-sm shadow-sm"
                >
                  <Icon className="h-4 w-4 text-primary" aria-hidden="true" />
                  {text}
                </li>
              ))}
            </ul>
            <div className="flex flex-wrap items-center gap-5">
              <Link to={user ? '/' : '/register'} className="btn-primary px-6 py-3 text-base">
                Get Started <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Link>
              {!user && (
                <Link to="/login" className="text-sm text-muted-foreground hover:text-primary">
                  I already have an account
                </Link>
              )}
            </div>
          </div>

          <ul className="flex flex-col gap-4">
            {FEATURES.map(({ icon: Icon, tint, title, text }) => (
              <li key={title} className="card flex gap-5 p-6">
                <span
                  className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${tint}`}
                >
                  <Icon className="h-5 w-5" aria-hidden="true" />
                </span>
                <div className="flex flex-col gap-1">
                  <h2 className="text-lg font-semibold">{title}</h2>
                  <p className="text-sm leading-relaxed text-muted-foreground">{text}</p>
                </div>
              </li>
            ))}
          </ul>
        </section>

        <section className="border-t border-border/60 bg-card/50 py-20">
          <div className="mx-auto flex max-w-4xl flex-col items-center gap-4 px-6 text-center">
            <h2 className="text-3xl font-bold sm:text-4xl">
              Ship the <em className="text-primary">bug report</em>, not the confusion.
            </h2>
            <p className="max-w-2xl text-lg text-muted-foreground">
              Submit your observation, review AI-highlighted fields, confirm the triage suggestions,
              and export a developer-ready report, in under a minute.
            </p>
            <ol className="mt-8 grid w-full max-w-3xl grid-cols-2 gap-4 sm:grid-cols-4">
              {STEPS.map((step, index) => (
                <li
                  key={step}
                  className="card flex flex-col items-center gap-2 px-4 py-6 transition hover:-translate-y-1 hover:shadow-lift"
                >
                  <span className="text-3xl font-bold text-primary/40">
                    {String(index + 1).padStart(2, '0')}
                  </span>
                  <span className="font-semibold">{step}</span>
                </li>
              ))}
            </ol>
          </div>
        </section>
      </main>

      <footer className="border-t border-border/60 py-6 text-center text-sm text-muted-foreground">
        © {new Date().getFullYear()} BugTriage · Built with{' '}
        <Heart className="inline h-4 w-4 fill-primary text-primary" aria-label="love" /> by the team
      </footer>
    </div>
  );
}

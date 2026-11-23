// Sign-in page (US-01).

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useLogin } from '@/hooks/useAuth';
import { ApiRequestError } from '@/lib/api';
import { ErrorState } from '@/components/states';
import { AuthLayout } from '@/components/layout/AuthLayout';
import { PasswordInput } from '@/components/PasswordInput';

const loginSchema = z.object({
  email: z.string().email('Enter a valid email address'),
  password: z.string().min(1, 'Enter your password'),
});

type LoginValues = z.infer<typeof loginSchema>;

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const login = useLogin();
  const justRegistered = Boolean(
    (location.state as { justRegistered?: boolean } | null)?.justRegistered,
  );

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginValues>({ resolver: zodResolver(loginSchema) });

  const onSubmit = handleSubmit((values) => {
    login.mutate(values, {
      onSuccess: () => navigate('/', { replace: true }),
    });
  });

  const serverError =
    login.error instanceof ApiRequestError
      ? login.error.message
      : login.error
        ? 'Something went wrong. Try again.'
        : null;

  return (
    <AuthLayout title="Welcome back" subtitle="Sign in to continue to BugTriage" active="signin">
      {justRegistered && (
        <p role="status" className="mb-4 rounded-lg bg-accent p-3 text-sm text-accent-foreground">
          Account created. Sign in to continue.
        </p>
      )}

      {serverError && (
        <div className="mb-4">
          <ErrorState message={serverError} />
        </div>
      )}

      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-5">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="email" className="text-sm font-medium">
            Email
          </label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            placeholder="you@example.com"
            aria-invalid={Boolean(errors.email)}
            aria-describedby={errors.email ? 'email-error' : undefined}
            className="field"
            {...register('email')}
          />
          {errors.email && (
            <p id="email-error" className="text-sm text-destructive">
              {errors.email.message}
            </p>
          )}
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="password" className="text-sm font-medium">
            Password
          </label>
          <PasswordInput
            id="password"
            autoComplete="current-password"
            aria-invalid={Boolean(errors.password)}
            aria-describedby={errors.password ? 'password-error' : undefined}
            {...register('password')}
          />
          {errors.password && (
            <p id="password-error" className="text-sm text-destructive">
              {errors.password.message}
            </p>
          )}
        </div>

        <button type="submit" disabled={login.isPending} className="btn-primary py-2.5">
          {login.isPending ? 'Signing in…' : 'Sign in'}
        </button>
      </form>

      <div className="my-5 flex items-center gap-3 text-xs text-muted-foreground">
        <span className="h-px flex-1 bg-border" />
        or
        <span className="h-px flex-1 bg-border" />
      </div>
      <p className="text-center text-sm text-muted-foreground">
        Don&apos;t have an account?{' '}
        <Link to="/register" className="font-medium text-primary hover:underline">
          Sign up
        </Link>
      </p>
    </AuthLayout>
  );
}

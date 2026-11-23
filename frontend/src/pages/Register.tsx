// Account creation page (US-01).

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Link, useNavigate } from 'react-router-dom';
import { useRegister } from '@/hooks/useAuth';
import { ApiRequestError } from '@/lib/api';
import { ErrorState } from '@/components/states';
import { AuthLayout } from '@/components/layout/AuthLayout';
import { PasswordInput } from '@/components/PasswordInput';

// Mirrors backend/app/schemas/core.py UserCreate (US-01 criterion 1). The
// confirmation only guards against a typo; it is never sent.
const registerSchema = z
  .object({
    email: z.string().email('Enter a valid email address'),
    password: z.string().min(8, 'Password must be at least 8 characters'),
    confirmPassword: z.string(),
  })
  .refine((values) => values.password === values.confirmPassword, {
    message: 'The two passwords do not match',
    path: ['confirmPassword'],
  });

type RegisterValues = z.infer<typeof registerSchema>;

export default function Register() {
  const navigate = useNavigate();
  const registerUser = useRegister();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterValues>({ resolver: zodResolver(registerSchema) });

  const onSubmit = handleSubmit(({ email, password }) => {
    registerUser.mutate(
      { email, password },
      {
        onSuccess: () => navigate('/login', { replace: true, state: { justRegistered: true } }),
      },
    );
  });

  const serverError =
    registerUser.error instanceof ApiRequestError
      ? registerUser.error.message
      : registerUser.error
        ? 'Something went wrong. Try again.'
        : null;

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Get started with BugTriage for free"
      active="signup"
    >
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
            autoComplete="new-password"
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

        <div className="flex flex-col gap-1.5">
          <label htmlFor="confirm-password" className="text-sm font-medium">
            Confirm Password
          </label>
          <PasswordInput
            id="confirm-password"
            autoComplete="new-password"
            aria-invalid={Boolean(errors.confirmPassword)}
            aria-describedby={errors.confirmPassword ? 'confirm-password-error' : undefined}
            {...register('confirmPassword')}
          />
          {errors.confirmPassword && (
            <p id="confirm-password-error" className="text-sm text-destructive">
              {errors.confirmPassword.message}
            </p>
          )}
        </div>

        <button type="submit" disabled={registerUser.isPending} className="btn-primary py-2.5">
          {registerUser.isPending ? 'Creating account…' : 'Create account'}
        </button>
      </form>

      <div className="my-5 flex items-center gap-3 text-xs text-muted-foreground">
        <span className="h-px flex-1 bg-border" />
        or
        <span className="h-px flex-1 bg-border" />
      </div>
      <p className="text-center text-sm text-muted-foreground">
        Already have an account?{' '}
        <Link to="/login" className="font-medium text-primary hover:underline">
          Sign in
        </Link>
      </p>
    </AuthLayout>
  );
}

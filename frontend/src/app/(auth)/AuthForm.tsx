"use client";

import Link from "next/link";
import { useActionState } from "react";

import { Button, ErrorBanner, Field, Input } from "@/components/ui";
import type { AuthFormState } from "./actions";

type Mode = "login" | "signup";

export function AuthForm({
  mode,
  action,
  next,
  notice,
}: {
  mode: Mode;
  action: (state: AuthFormState, formData: FormData) => Promise<AuthFormState>;
  next?: string;
  notice?: string;
}) {
  // useActionState runs the Server Action on submit and gives us its return
  // value (errors) plus a `pending` flag for the button.
  const [state, formAction, pending] = useActionState(action, undefined);
  const errors = state?.fieldErrors ?? {};

  return (
    <form action={formAction} className="flex flex-col gap-4" noValidate>
      {notice ? <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:bg-amber-950 dark:text-amber-200">{notice}</p> : null}
      <ErrorBanner message={state?.error} />
      {next ? <input type="hidden" name="next" value={next} /> : null}
      {mode === "signup" ? (
        <Field label="Company name" htmlFor="organization_name" error={errors.organization_name}>
          <Input id="organization_name" name="organization_name" required autoComplete="organization" />
        </Field>
      ) : null}
      <Field label="Email" htmlFor="email" error={errors.email}>
        <Input id="email" name="email" type="email" required autoComplete="email" defaultValue={state?.email} />
      </Field>
      <Field label="Password" htmlFor="password" error={errors.password}>
        <Input
          id="password"
          name="password"
          type="password"
          required
          minLength={mode === "signup" ? 12 : undefined}
          autoComplete={mode === "signup" ? "new-password" : "current-password"}
        />
      </Field>
      {mode === "signup" ? <p className="-mt-2 text-xs text-zinc-500">At least 12 characters. A short phrase works well.</p> : null}
      <Button type="submit" disabled={pending}>
        {pending ? "Please wait…" : mode === "login" ? "Log in" : "Create account"}
      </Button>
      <p className="text-center text-sm text-zinc-600 dark:text-zinc-400">
        {mode === "login" ? (
          <>No account yet? <Link className="underline" href="/signup">Sign up</Link></>
        ) : (
          <>Already have an account? <Link className="underline" href="/login">Log in</Link></>
        )}
      </p>
    </form>
  );
}

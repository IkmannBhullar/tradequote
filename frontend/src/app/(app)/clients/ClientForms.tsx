"use client";

import { useActionState } from "react";

import { Button, ErrorBanner, Field, Input } from "@/components/ui";
import type { Client } from "@/lib/api/types";
import type { FormState } from "./actions";

type FormAction = (state: FormState, formData: FormData) => Promise<FormState>;

/** Create or edit a client (same fields either way). */
export function ClientForm({ action, client, submitLabel }: { action: FormAction; client?: Client; submitLabel: string }) {
  const [state, formAction, pending] = useActionState(action, undefined);
  const errors = state?.fieldErrors ?? {};
  return (
    <form action={formAction} className="grid gap-3 sm:grid-cols-2">
      <div className="sm:col-span-2"><ErrorBanner message={state?.error} /></div>
      <Field label="Name" htmlFor="name" error={errors.name}>
        <Input id="name" name="name" required defaultValue={client?.name} />
      </Field>
      <Field label="Email" htmlFor="email" error={errors.email}>
        <Input id="email" name="email" type="email" defaultValue={client?.email ?? ""} />
      </Field>
      <Field label="Phone" htmlFor="phone" error={errors.phone}>
        <Input id="phone" name="phone" type="tel" defaultValue={client?.phone ?? ""} />
      </Field>
      <Field label="Address" htmlFor="address" error={errors.address}>
        <Input id="address" name="address" defaultValue={client?.address ?? ""} />
      </Field>
      <div className="flex items-center gap-3 sm:col-span-2">
        <Button type="submit" disabled={pending}>{pending ? "Saving…" : submitLabel}</Button>
        {state?.saved ? <span role="status" className="text-sm text-green-700 dark:text-green-400">Saved.</span> : null}
      </div>
    </form>
  );
}

export function DeleteClientButton({ action }: { action: (state: FormState) => Promise<FormState> }) {
  const [state, formAction, pending] = useActionState(action, undefined);
  return (
    <form action={formAction} className="flex flex-col items-end gap-2">
      <Button type="submit" variant="danger" disabled={pending}>Delete client</Button>
      <ErrorBanner message={state?.error} />
    </form>
  );
}

export function NewJobForm({ action }: { action: FormAction }) {
  const [state, formAction, pending] = useActionState(action, undefined);
  const errors = state?.fieldErrors ?? {};
  return (
    <form action={formAction} className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
      <div className="sm:col-span-3"><ErrorBanner message={state?.error} /></div>
      <Field label="Job title" htmlFor="title" error={errors.title}>
        <Input id="title" name="title" required placeholder="Repaint living room" />
      </Field>
      <Field label="Job address (if different)" htmlFor="job_address" error={errors.address}>
        <Input id="job_address" name="address" />
      </Field>
      <Button type="submit" disabled={pending}>New job</Button>
    </form>
  );
}

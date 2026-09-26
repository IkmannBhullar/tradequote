"use client";

import { useActionState } from "react";

import { Button, ErrorBanner, Field, Input } from "@/components/ui";
import type { Job } from "@/lib/api/types";
import type { FormState } from "../../clients/actions";

export function JobForm({ job, action }: { job: Job; action: (state: FormState, formData: FormData) => Promise<FormState> }) {
  const [state, formAction, pending] = useActionState(action, undefined);
  const errors = state?.fieldErrors ?? {};
  return (
    <form action={formAction} className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
      <div className="sm:col-span-3"><ErrorBanner message={state?.error} /></div>
      <Field label="Title" htmlFor="title" error={errors.title}>
        <Input id="title" name="title" required defaultValue={job.title} />
      </Field>
      <Field label="Address" htmlFor="address" error={errors.address}>
        <Input id="address" name="address" defaultValue={job.address ?? ""} />
      </Field>
      <Button type="submit" variant="secondary" disabled={pending}>{state?.saved ? "Saved" : "Save"}</Button>
    </form>
  );
}

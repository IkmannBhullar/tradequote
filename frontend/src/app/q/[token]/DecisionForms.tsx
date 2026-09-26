"use client";

import { useActionState } from "react";

import { Button, ErrorBanner, Field, Input } from "@/components/ui";
import type { DecisionState } from "./actions";

type Action = (state: DecisionState, formData: FormData) => Promise<DecisionState>;

export function DecisionForms({ approve, decline }: { approve: Action; decline: Action }) {
  const [approveState, approveAction, approving] = useActionState(approve, undefined);
  const [declineState, declineAction, declining] = useActionState(decline, undefined);
  const approveErrors = approveState?.fieldErrors ?? {};
  const busy = approving || declining;

  return (
    <div className="flex flex-col gap-4">
      <form action={approveAction} className="flex flex-col gap-3 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
        <h2 className="text-base font-semibold">Approve this quote</h2>
        <ErrorBanner message={approveState?.error} />
        <Field label="Your full name" htmlFor="approve-name" error={approveErrors.name}>
          <Input id="approve-name" name="name" required autoComplete="name" />
        </Field>
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" name="accept_terms" required className="mt-1" />
          <span>I agree to this quote, including the deposit shown, and understand that typing my name serves as my signature.</span>
        </label>
        {approveErrors.accept_terms ? <p className="text-sm text-red-600">Please tick the box to approve.</p> : null}
        <div>
          <Button type="submit" disabled={busy}>{approving ? "Approving…" : "Approve quote"}</Button>
        </div>
      </form>

      {/* Declining is secondary, so it's tucked away until needed. */}
      <details className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
        <summary className="cursor-pointer text-sm font-medium">Decline this quote</summary>
        <form action={declineAction} className="mt-3 flex flex-col gap-3">
          <ErrorBanner message={declineState?.error} />
          <Field label="Your full name" htmlFor="decline-name" error={declineState?.fieldErrors?.name}>
            <Input id="decline-name" name="name" required autoComplete="name" />
          </Field>
          <Field label="Reason (optional)" htmlFor="decline-reason">
            <Input id="decline-reason" name="reason" />
          </Field>
          <div>
            <Button type="submit" variant="danger" disabled={busy}>{declining ? "Declining…" : "Decline quote"}</Button>
          </div>
        </form>
      </details>
    </div>
  );
}

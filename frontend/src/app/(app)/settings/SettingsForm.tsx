"use client";

import { useActionState } from "react";

import { Button, ErrorBanner, Field, Input } from "@/components/ui";
import type { Organization } from "@/lib/api/types";
import { centsToDollars, fractionToPercent } from "@/lib/money";
import { saveSettings } from "./actions";

export function SettingsForm({ organization }: { organization: Organization }) {
  const [state, action, pending] = useActionState(saveSettings, undefined);
  const errors = state?.fieldErrors ?? {};
  return (
    <form action={action} className="flex max-w-md flex-col gap-4">
      <ErrorBanner message={state?.error} />
      {state?.saved ? <p role="status" className="text-sm text-green-700 dark:text-green-400">Saved.</p> : null}
      <Field label="Company name" htmlFor="name" error={errors.name}>
        <Input id="name" name="name" defaultValue={organization.name} required />
      </Field>
      <Field label="Labor rate ($ per hour)" htmlFor="labor_rate" error={errors.default_labor_rate_cents}>
        <Input
          id="labor_rate"
          name="labor_rate"
          inputMode="decimal"
          defaultValue={centsToDollars(organization.default_labor_rate_cents)}
        />
      </Field>
      <Field label="Tax rate (%)" htmlFor="tax_rate" error={errors.tax_rate}>
        <Input id="tax_rate" name="tax_rate" inputMode="decimal" defaultValue={fractionToPercent(organization.tax_rate)} />
      </Field>
      <p className="text-xs text-zinc-500">New quotes use these rates. Existing quotes keep the rates they were created with.</p>
      <div>
        <Button type="submit" disabled={pending}>{pending ? "Saving…" : "Save settings"}</Button>
      </div>
    </form>
  );
}

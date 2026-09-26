"use server";

import { refresh } from "next/cache";

import { api, toActionResult } from "@/lib/api/client";
import type { FieldErrors } from "@/lib/api/errors";
import { dollarsToCents, percentToFraction } from "@/lib/money";

export type SettingsState = { error?: string; fieldErrors?: FieldErrors; saved?: boolean } | undefined;

export async function saveSettings(_state: SettingsState, formData: FormData): Promise<SettingsState> {
  const laborRate = dollarsToCents(String(formData.get("labor_rate") ?? ""));
  const taxRate = percentToFraction(String(formData.get("tax_rate") ?? ""));
  const fieldErrors: FieldErrors = {};
  if (laborRate === null) fieldErrors.default_labor_rate_cents = "Enter an amount like 65 or 65.50";
  if (taxRate === null) fieldErrors.tax_rate = "Enter a percent like 5 or 7.5";
  if (laborRate === null || taxRate === null) return { error: "Please fix the highlighted fields.", fieldErrors };

  const result = toActionResult(
    await (await api()).PATCH("/organization", {
      body: {
        name: String(formData.get("name") ?? ""),
        default_labor_rate_cents: laborRate,
        tax_rate: taxRate,
      },
    }),
  );
  if (!result.ok) return { error: result.error, fieldErrors: result.fieldErrors };
  refresh(); // re-render (e.g. the company name in the nav)
  return { saved: true };
}

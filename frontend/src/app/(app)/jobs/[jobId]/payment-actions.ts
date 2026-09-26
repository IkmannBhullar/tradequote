"use server";

import { refresh } from "next/cache";

import { api, toActionResult } from "@/lib/api/client";
import type { ActionResult } from "@/lib/api/errors";
import type { JobPayments } from "@/lib/api/types";

export type PaymentInput = {
  amount_cents: number;
  kind: "deposit" | "final";
  method: string | null;
  received_on: string; // "YYYY-MM-DD"
};

// Each returns the job's payments and new balance. refresh() re-renders the
// rest of the page too, since a payment can move the job to "paid".

export async function recordPayment(jobId: string, input: PaymentInput): Promise<ActionResult<JobPayments>> {
  const result = toActionResult(
    await (await api()).POST("/jobs/{job_id}/payments", { params: { path: { job_id: jobId } }, body: input }),
  );
  if (result.ok) refresh();
  return result;
}

export async function voidPayment(jobId: string, paymentId: string, reason: string): Promise<ActionResult<JobPayments>> {
  const result = toActionResult(
    await (await api()).POST("/jobs/{job_id}/payments/{payment_id}/void", {
      params: { path: { job_id: jobId, payment_id: paymentId } },
      body: { reason },
    }),
  );
  if (result.ok) refresh();
  return result;
}

"use server";

import { refresh } from "next/cache";
import { redirect } from "next/navigation";

import { api, toActionResult } from "@/lib/api/client";
import type { JobStatus } from "@/lib/api/types";
import type { FormState } from "../clients/actions";

/** Board move. The backend decides whether the move is allowed. */
export async function moveJob(jobId: string, status: JobStatus): Promise<void> {
  const result = toActionResult(
    await (await api()).PATCH("/jobs/{job_id}", { params: { path: { job_id: jobId } }, body: { status } }),
  );
  // Only offered moves are shown, so a failure here is unexpected (e.g.
  // someone else moved the job meanwhile): surface it via the error page.
  if (!result.ok) throw new Error(result.error);
  refresh();
}

export async function updateJob(jobId: string, _state: FormState, formData: FormData): Promise<FormState> {
  const address = String(formData.get("address") ?? "").trim();
  const result = toActionResult(
    await (await api()).PATCH("/jobs/{job_id}", {
      params: { path: { job_id: jobId } },
      body: { title: String(formData.get("title") ?? ""), address: address === "" ? null : address },
    }),
  );
  if (!result.ok) return { error: result.error, fieldErrors: result.fieldErrors };
  refresh();
  return { saved: true };
}

export async function createQuote(jobId: string): Promise<void> {
  const result = toActionResult(
    await (await api()).POST("/jobs/{job_id}/quotes", { params: { path: { job_id: jobId } } }),
  );
  if (!result.ok) throw new Error(result.error);
  redirect(`/quotes/${result.data.id}`);
}

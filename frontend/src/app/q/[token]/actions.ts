"use server";

import { refresh } from "next/cache";

import { parseApiError, type FieldErrors } from "@/lib/api/errors";
import { publicApi, quoteToken } from "@/lib/api/public";

export type DecisionState = { error?: string; fieldErrors?: FieldErrors } | undefined;

// No login here: the token (bound in by the page, and already in the URL the
// client opened) is the only credential, and FastAPI checks it every time.

export async function approveQuote(token: string, _state: DecisionState, formData: FormData): Promise<DecisionState> {
  const { data, error, response } = await (await publicApi()).POST("/public/quote/approve", {
    ...quoteToken(token),
    body: {
      name: String(formData.get("name") ?? ""),
      // An unticked checkbox is simply absent from the form data. Sending
      // false lets the API reject it with a field error.
      accept_terms: (formData.get("accept_terms") === "on") as true,
    },
  });
  if (!data) return parseApiError(error, response.status);
  refresh(); // re-render the page, now showing "Approved"
  return undefined;
}

export async function declineQuote(token: string, _state: DecisionState, formData: FormData): Promise<DecisionState> {
  const reason = String(formData.get("reason") ?? "").trim();
  const { data, error, response } = await (await publicApi()).POST("/public/quote/decline", {
    ...quoteToken(token),
    body: { name: String(formData.get("name") ?? ""), reason: reason === "" ? null : reason },
  });
  if (!data) return parseApiError(error, response.status);
  refresh();
  return undefined;
}

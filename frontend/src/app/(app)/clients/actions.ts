"use server";

import { refresh } from "next/cache";
import { redirect } from "next/navigation";

import { api, toActionResult } from "@/lib/api/client";
import type { FieldErrors } from "@/lib/api/errors";

export type FormState = { error?: string; fieldErrors?: FieldErrors; saved?: boolean } | undefined;

// Empty optional inputs become null ("no email"), not "".
function optional(formData: FormData, name: string): string | null {
  const value = String(formData.get(name) ?? "").trim();
  return value === "" ? null : value;
}

function clientBody(formData: FormData) {
  return {
    name: String(formData.get("name") ?? ""),
    email: optional(formData, "email"),
    phone: optional(formData, "phone"),
    address: optional(formData, "address"),
  };
}

export async function createClient(_state: FormState, formData: FormData): Promise<FormState> {
  const result = toActionResult(await (await api()).POST("/clients", { body: clientBody(formData) }));
  if (!result.ok) return { error: result.error, fieldErrors: result.fieldErrors };
  redirect(`/clients/${result.data.id}`);
}

export async function updateClient(clientId: string, _state: FormState, formData: FormData): Promise<FormState> {
  const result = toActionResult(
    await (await api()).PATCH("/clients/{client_id}", {
      params: { path: { client_id: clientId } },
      body: clientBody(formData),
    }),
  );
  if (!result.ok) return { error: result.error, fieldErrors: result.fieldErrors };
  refresh();
  return { saved: true };
}

export async function deleteClient(clientId: string, _state: FormState): Promise<FormState> {
  const result = toActionResult(
    await (await api()).DELETE("/clients/{client_id}", { params: { path: { client_id: clientId } } }),
  );
  if (!result.ok) return { error: result.error };
  redirect("/clients");
}

export async function createJob(clientId: string, _state: FormState, formData: FormData): Promise<FormState> {
  const result = toActionResult(
    await (await api()).POST("/jobs", {
      body: {
        client_id: clientId,
        title: String(formData.get("title") ?? ""),
        address: optional(formData, "address"),
      },
    }),
  );
  if (!result.ok) return { error: result.error, fieldErrors: result.fieldErrors };
  redirect(`/jobs/${result.data.id}`);
}

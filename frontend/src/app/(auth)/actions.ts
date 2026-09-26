"use server";

import createClient from "openapi-fetch";
import { redirect } from "next/navigation";

import type { paths } from "@/lib/api/schema";
import { parseApiError, type FieldErrors } from "@/lib/api/errors";
import { apiUrl } from "@/lib/config";
import { clearSession, setSession } from "@/lib/session";

export type AuthFormState = { error?: string; fieldErrors?: FieldErrors; email?: string } | undefined;

// Only allow same-site relative paths, so a crafted ?next=https://evil.com
// link can't bounce users to another site after login (open redirect).
function safeNext(next: FormDataEntryValue | null): string {
  const path = typeof next === "string" ? next : "";
  return path.startsWith("/") && !path.startsWith("//") ? path : "/jobs";
}

function field(formData: FormData, name: string): string {
  const value = formData.get(name);
  return typeof value === "string" ? value : "";
}

export async function login(_state: AuthFormState, formData: FormData): Promise<AuthFormState> {
  const email = field(formData, "email");
  const client = createClient<paths>({ baseUrl: apiUrl(), cache: "no-store" });
  const { data, error, response } = await client.POST("/auth/login", {
    body: { email, password: field(formData, "password") },
  });
  if (!data) return { ...parseApiError(error, response.status), email };

  await setSession(data.access_token, data.expires_in);
  redirect(safeNext(formData.get("next")));
}

export async function signup(_state: AuthFormState, formData: FormData): Promise<AuthFormState> {
  const email = field(formData, "email");
  const client = createClient<paths>({ baseUrl: apiUrl(), cache: "no-store" });
  const { data, error, response } = await client.POST("/auth/signup", {
    body: {
      organization_name: field(formData, "organization_name"),
      email,
      password: field(formData, "password"),
    },
  });
  if (!data) return { ...parseApiError(error, response.status), email };

  await setSession(data.access_token, data.expires_in);
  // New organizations start at $0/hour: send them to set their rates first.
  redirect("/settings?welcome=1");
}

export async function logout(): Promise<void> {
  await clearSession();
  redirect("/login");
}

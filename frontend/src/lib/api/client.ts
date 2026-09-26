import "server-only";

import createClient from "openapi-fetch";
import { notFound, redirect } from "next/navigation";

import { apiUrl } from "@/lib/config";
import { getToken } from "@/lib/session";
import { type ActionResult, parseApiError } from "./errors";
import type { paths } from "./schema";

/**
 * A typed FastAPI client that sends the current user's token.
 *
 * Every URL, parameter, and body is checked against the backend's OpenAPI
 * schema at compile time: rename a field in FastAPI, regenerate the types,
 * and TypeScript points at every place that breaks.
 */
export async function api() {
  const token = await getToken();
  return createClient<paths>({
    baseUrl: apiUrl(),
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    // Always fresh data: quotes change constantly and are per-user.
    cache: "no-store",
  });
}

type FetchResult<T> = { data?: T; error?: unknown; response: Response };

// The session is gone or expired: clear the cookie and go to login. (Cookies
// can't be deleted while rendering a page, so a route handler does it.)
function sessionExpired(): never {
  redirect("/logout?expired=1");
}

/** For pages: return the data, or show the 404 page / go to login / throw. */
export function unwrap<T>(result: FetchResult<T>): T {
  if (result.response.status === 401) sessionExpired();
  if (result.response.status === 404) notFound();
  if (result.data === undefined) {
    throw new Error(`API ${result.response.status}: ${parseApiError(result.error, result.response.status).error}`);
  }
  return result.data;
}

/** For Server Actions: data, or an error message the form can display. */
export function toActionResult<T>(result: FetchResult<T>): ActionResult<T> {
  if (result.response.status === 401) sessionExpired();
  if (result.data !== undefined) return { ok: true, data: result.data };
  // Some successful responses (204 No Content) have no body.
  if (result.response.ok) return { ok: true, data: undefined as T };
  return { ok: false, ...parseApiError(result.error, result.response.status) };
}

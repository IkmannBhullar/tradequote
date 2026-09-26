import "server-only";

import createClient from "openapi-fetch";
import { headers } from "next/headers";

import { apiUrl } from "@/lib/config";
import type { paths } from "./schema";

/**
 * FastAPI client for the public quote pages (no login).
 *
 * X-Forwarded-For passes on the visitor's IP: FastAPI rate-limits public
 * requests per IP, and without this every visitor would look like this one
 * Next.js server and share a single limit.
 */
export async function publicApi() {
  const forwardedFor = (await headers()).get("x-forwarded-for");
  return createClient<paths>({
    baseUrl: apiUrl(),
    headers: forwardedFor ? { "X-Forwarded-For": forwardedFor } : {},
    cache: "no-store",
  });
}

/**
 * The link token, sent as the X-Quote-Token header on each call: never in
 * the URL path, so it stays out of FastAPI's access logs. The OpenAPI types
 * mark this header as required, so a call without it doesn't compile.
 */
export function quoteToken(token: string) {
  return { params: { header: { "X-Quote-Token": token } } };
}

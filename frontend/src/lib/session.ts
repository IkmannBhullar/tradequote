import "server-only";

import { cookies } from "next/headers";

// The login token lives ONLY in this cookie, set by the Next.js server:
// - httpOnly: browser JavaScript can't read it, so an XSS bug can't steal it.
// - sameSite "lax": not sent on cross-site POSTs (CSRF protection, alongside
//   Next's Origin check on Server Actions).
// - secure in production: only sent over HTTPS.
export const SESSION_COOKIE = "tq_session";

export async function getToken(): Promise<string | undefined> {
  return (await cookies()).get(SESSION_COOKIE)?.value;
}

/** Call only from Server Actions or Route Handlers (Next.js rule). */
export async function setSession(token: string, expiresInSeconds: number): Promise<void> {
  (await cookies()).set(SESSION_COOKIE, token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    // The cookie disappears when the token would stop working anyway.
    maxAge: expiresInSeconds,
  });
}

export async function clearSession(): Promise<void> {
  (await cookies()).delete(SESSION_COOKIE);
}

import { type NextRequest, NextResponse } from "next/server";

import { clearSession } from "@/lib/session";

// Used when the API says the session is invalid (see lib/api/client.ts).
// Cookies can't be deleted while a page renders, so pages redirect here and
// this route handler deletes it. (User-initiated logout is a POST action.)
export async function GET(request: NextRequest) {
  await clearSession();
  const login = new URL("/login", request.url);
  if (request.nextUrl.searchParams.has("expired")) login.searchParams.set("expired", "1");
  return NextResponse.redirect(login);
}

import { type NextRequest, NextResponse } from "next/server";

// Runs before every matched request (Next.js 16 renamed "middleware" to
// "proxy"). It only does a cheap, OPTIMISTIC check: is there a session cookie
// at all? The real check happens on every API call, where FastAPI verifies
// the token; an expired or forged cookie gets past here but fails there.
const SESSION_COOKIE = "tq_session"; // same name as lib/session.ts
const PUBLIC_PATHS = ["/login", "/signup", "/logout"];

export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const hasSession = request.cookies.has(SESSION_COOKIE);
  const isPublic = PUBLIC_PATHS.some((path) => pathname === path || pathname.startsWith(`${path}/`));

  if (!hasSession && !isPublic) {
    const login = new URL("/login", request.url);
    // Come back to the page they asked for after logging in.
    login.searchParams.set("next", pathname + search);
    return NextResponse.redirect(login);
  }
  if (hasSession && (pathname === "/login" || pathname === "/signup")) {
    return NextResponse.redirect(new URL("/jobs", request.url));
  }
  return NextResponse.next();
}

export const config = {
  // Skip Next's own assets and static files, or pages would load unstyled.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|ico)$).*)"],
};

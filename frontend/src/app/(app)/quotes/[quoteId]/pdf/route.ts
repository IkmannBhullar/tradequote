import { type NextRequest, NextResponse } from "next/server";

import { api } from "@/lib/api/client";

// Streams the contractor's quote PDF through the Next.js server, which adds
// the login token (the browser never holds it). URL: /quotes/<id>/pdf
export async function GET(request: NextRequest, context: RouteContext<"/quotes/[quoteId]/pdf">) {
  const { quoteId } = await context.params;
  const { response } = await (await api()).GET("/quotes/{quote_id}/pdf", {
    params: { path: { quote_id: quoteId } },
    parseAs: "stream",
  });
  if (response.status === 401) return NextResponse.redirect(new URL("/logout?expired=1", request.url));
  if (!response.ok) return new NextResponse("Quote not found", { status: response.status });
  return new NextResponse(response.body, {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": response.headers.get("content-disposition") ?? "inline",
      "Cache-Control": "private, no-store",
    },
  });
}

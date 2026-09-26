import { type NextRequest, NextResponse } from "next/server";

import { publicApi, quoteToken } from "@/lib/api/public";

// The client's PDF download, streamed through the Next.js server (which
// passes the token to FastAPI in a header, not a URL). URL: /q/<token>/pdf
export async function GET(_request: NextRequest, context: RouteContext<"/q/[token]/pdf">) {
  const { token } = await context.params;
  const { response } = await (await publicApi()).GET("/public/quote/pdf", {
    ...quoteToken(token),
    parseAs: "stream",
  });
  if (!response.ok) return new NextResponse("This link isn't valid or has expired.", { status: response.status });
  return new NextResponse(response.body, {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": response.headers.get("content-disposition") ?? "inline",
      "Cache-Control": "private, no-store",
      "Referrer-Policy": "no-referrer",
      "X-Robots-Tag": "noindex",
    },
  });
}

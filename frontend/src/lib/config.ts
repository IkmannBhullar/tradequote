import "server-only";

// Where the Next.js server reaches the FastAPI backend. Server-only: the
// browser never talks to FastAPI directly (backend-for-frontend pattern).
export function apiUrl(): string {
  const url = process.env.API_URL;
  if (url) return url;
  // Convenience default for `npm run dev`; production must configure it.
  if (process.env.NODE_ENV !== "production") return "http://localhost:8000";
  throw new Error("API_URL is not set");
}

// This app's own public address, used to build client links (/q/<token>).
export function appUrl(): string {
  const url = process.env.APP_URL;
  if (url) return url.replace(/\/$/, "");
  if (process.env.NODE_ENV !== "production") return "http://localhost:3000";
  throw new Error("APP_URL is not set");
}

/**
 * Called once at server startup (src/instrumentation.ts). In production,
 * missing settings stop the server from starting at all, instead of
 * surfacing later as a failed "Send quote" click.
 */
export function assertProductionConfig(): void {
  if (process.env.NODE_ENV !== "production") return;
  const missing = ["API_URL", "APP_URL"].filter((name) => !process.env[name]);
  if (missing.length > 0) {
    throw new Error(`Missing required environment variables: ${missing.join(", ")} (see frontend/.env.example)`);
  }
}

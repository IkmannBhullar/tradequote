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

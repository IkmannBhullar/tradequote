// Runs once when a Next.js server starts, before it handles any request.
export async function register() {
  // Only the Node.js server runtime reads our server config.
  if (process.env.NEXT_RUNTIME !== "nodejs") return;
  const { assertProductionConfig } = await import("@/lib/config");
  assertProductionConfig();
}

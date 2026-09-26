import { defineConfig, devices } from "@playwright/test";

// End-to-end tests: a real browser against the real stack (production
// Next.js build + FastAPI + Postgres). Run with `make e2e`, which builds the
// app and prepares the database first.
const CI = Boolean(process.env.CI);

export default defineConfig({
  testDir: "./e2e",
  retries: CI ? 1 : 0,
  reporter: CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: "http://localhost:3000",
    // On failure, keep a trace (DOM snapshots, network, console) to debug with.
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  // Playwright starts both servers and waits until they respond.
  webServer: [
    {
      command: "uv run uvicorn app.main:app --port 8000",
      cwd: "../backend",
      url: "http://localhost:8000/health",
      reuseExistingServer: !CI,
      timeout: 60_000,
    },
    {
      command: "npm run start",
      url: "http://localhost:3000/login",
      reuseExistingServer: !CI,
      timeout: 60_000,
      env: { API_URL: "http://localhost:8000", APP_URL: "http://localhost:3000" },
    },
  ],
});

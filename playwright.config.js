import { defineConfig } from "@playwright/test";

/**
 * E2E config for PathForge AI. Starts (or reuses) the FastAPI backend and the
 * Vite dev server, then runs browser tests against the live app.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:5173",
    headless: true,
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: ".venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8010",
      url: "http://127.0.0.1:8010/api/health",
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: "npm run dev",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
});

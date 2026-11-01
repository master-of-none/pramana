import { defineConfig, devices } from "@playwright/test";

// Browser regressions against the deterministic fixture server (tests/manual_chat_server.py):
// no downloaded books, models or network. Build the UI first: `npm run build`.
const PORT = 8011;

export default defineConfig({
  testDir: "e2e",
  // The server answers one chat at a time (a semaphore), so tests run one by one.
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "desktop",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } },
    },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
  webServer: {
    command: `uv run python tests/manual_chat_server.py --port ${PORT}`,
    cwd: "..",
    url: `http://127.0.0.1:${PORT}/api/status`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});

import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:5173",
    ...devices["iPhone 13"],
    browserName: "chromium",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "npm run dev -- --port 5173",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: !process.env.CI,
    },
    {
      command:
        "../.venv/bin/uvicorn app.api:app --app-dir ../backend --port 8000 --no-access-log",
      url: "http://127.0.0.1:8000/api/health",
      reuseExistingServer: !process.env.CI,
      env: {
        ENVIRONMENT: "development",
        DEV_AUTH: "true",
        ADMIN_IDS: "900",
        DATABASE_URL:
          process.env.DATABASE_URL ||
          "postgresql+asyncpg://postgres:test-only-password@127.0.0.1:55432/postgres",
        REDIS_URL: process.env.REDIS_URL || "redis://127.0.0.1:56379/14",
      },
    },
  ],
});

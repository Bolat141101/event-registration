import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  timeout: 90000,
  expect: { timeout: 12000 },
  reporter: 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL,
    viewport: { width: 1280, height: 900 },
    trace: 'off',
    screenshot: 'off',
    video: 'off',
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
      : {},
  },
});

import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',

  fullyParallel: true,

  forbidOnly: !!process.env.CI,

  retries: process.env.CI ? 2 : 0,

  workers: process.env.CI ? 2 : undefined,

  reporter: 'html',

  use: {
    baseURL:
      process.env.PLAYWRIGHT_BASE_URL ??
      'http://localhost:5173',

    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },

  projects: [
    {
      name: 'setup',

      testMatch: /auth\.setup\.ts/,
    },

    {
      name: 'chromium',

      testMatch: /.*\.spec\.ts/,

      dependencies: ['setup'],

      use: {
        ...devices['Desktop Chrome'],

        storageState: 'playwright/.auth/user.json',
      },
    },
  ],
});
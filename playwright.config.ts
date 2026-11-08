import { defineConfig, devices } from '@playwright/test';
import dotenv from 'dotenv';
import path from 'path';

// Đọc file .env
dotenv.config({ path: path.resolve(__dirname, '.env') });


export default defineConfig({
  // Thư mục chứa các Test Case
  testDir: './tests',

  // Chạy tuần tự để tránh xung đột dữ liệu
  fullyParallel: false,
  workers: 1,

  // Không tự động chạy lại khi Failed
  retries: 0,

  // Báo cáo
  reporter: [
    ['list'],
    ['html', { open: 'never' }],
  ],

  // Cấu hình trình duyệt
  use: {
    baseURL: 'http://localhost:5173',

    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },

  projects: [
    {
      name: 'setup-user',
      testMatch: /auth\.setup\.ts/,
      use: {
        ...devices['Desktop Chrome'],
      },
    },
    {
      name: 'chromium',
      testIgnore: /video-search\.spec\.ts/,
      use: {
        ...devices['Desktop Chrome'],
      },
    },
    {
      name: 'video-authenticated',

      testMatch: /video-search\.spec\.ts/,

      dependencies: ['setup-user'],

      use: {
        ...devices['Desktop Chrome'],

        storageState: 'playwright/.auth/user.json',
      },
    },
  ],
});
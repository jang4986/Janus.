import { defineConfig, devices } from '@playwright/test';

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
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
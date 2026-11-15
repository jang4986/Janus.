
import { test as setup, expect } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';

const authFile = path.resolve(
  process.cwd(),
  'playwright/.auth/user.json'
);

function getRequiredEnv(name: string): string {
  const value = process.env[name];

  if (!value) {
    throw new Error(`Missing environment variable: ${name}`);
  }

  return value;
}

setup('Authenticate as E2E User', async ({ page }) => {
  const email = getRequiredEnv('E2E_USER_EMAIL');
  const password = getRequiredEnv('E2E_USER_PASSWORD');

  // 1. Mở trang đăng nhập
  await page.goto('/');

  await page.getByRole('link', { name: 'Đăng nhập' }).click();

  // 2. Nhập thông tin
  await page.getByRole('textbox', { name: 'Email' })
    .fill(email);

  await page.getByRole('textbox', { name: 'Mật khẩu' })
    .fill(password);

  await page.getByRole('button', { name: 'Đăng nhập' }).click();

  // 3. Xác nhận đăng nhập
  await expect(page).toHaveURL('/', {
    timeout: 15000,
  });

  const profileLink = page
    .getByRole('navigation', { name: 'Điều hướng chính' })
    .getByRole('link', { name: 'Hồ sơ' });

  await expect(profileLink).toBeVisible();

  // 4. Lưu Authentication State
  await mkdir(path.dirname(authFile), {
    recursive: true,
  });

  await page.context().storageState({
    path: authFile,
  });
});

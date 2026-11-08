
import { test as setup, expect } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';

const authFile = path.resolve(
  process.cwd(),
  'playwright/.auth/user.json'
);

setup('Authenticate as User', async ({ page }) => {
  // 1. Lấy thông tin tài khoản từ .env
  const email = process.env.E2E_USER_EMAIL;
  const password = process.env.E2E_USER_PASSWORD;

  if (!email || !password) {
    throw new Error('Missing User test credentials in .env');
  }

  // 2. Đăng nhập
  await page.goto('/');

  await page.getByRole('link', { name: 'Đăng nhập' }).click();

  await page.getByRole('textbox', { name: 'Email' }).fill(email);

  await page.getByRole('textbox', { name: 'Mật khẩu' }).fill(password);

  await page.getByRole('button', { name: 'Đăng nhập' }).click();

  // 3. Xác nhận đăng nhập thành công
  await expect(page).toHaveURL('/', {
    timeout: 15000,
  });

  const profileLink = page
    .getByRole('navigation', { name: 'Điều hướng chính' })
    .getByRole('link', { name: 'Hồ sơ' });

  await expect(profileLink).toBeVisible();

  // 4. Lưu Authentication State
  await mkdir(path.dirname(authFile), { recursive: true });

  await page.context().storageState({
    path: authFile,
  });
});

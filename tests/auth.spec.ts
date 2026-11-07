
import { test, expect } from '@playwright/test';
import { randomUUID } from 'node:crypto';

test('REG-01 - Đăng ký tài khoản với thông tin hợp lệ', async ({ page }) => {
  // Test data

  const username = `qa-${randomUUID()}`;
  const email = `${username}@example.com`;
  const password = 'qwe123!@#';

  // 1. Mở trang đăng ký
  await page.goto('/');

  await page.getByRole('link', { name: 'Đăng nhập' }).click();
  await page.getByRole('link', { name: 'Đăng ký' }).click();

  // 2. Nhập thông tin đăng ký
  await page.getByRole('textbox', { name: 'Username' })
    .fill(username);

  await page.getByRole('textbox', { name: 'Email' })
    .fill(email);

  await page.getByRole('textbox', { name: 'Mật khẩu' })
    .fill(password);

  // 3. Gửi yêu cầu đăng ký
  await page.getByRole('button', { name: 'Đăng ký' }).click();

  // 4. Xác nhận chuyển về trang chủ sau đăng ký
    await expect(page).toHaveURL('/', {
    timeout: 15000,
    });

  // 5. Xác nhận trạng thái đã đăng nhập
  const profileLink = page
    .getByRole('navigation', { name: 'Điều hướng chính' })
    .getByRole('link', { name: 'Hồ sơ' });

  await expect(profileLink).toBeVisible();

  // 6. Truy cập Profile
  await profileLink.click();

  // 7. Xác nhận Username được lưu chính xác
  await expect(
    page.getByRole('heading', {
      name: username,
      exact: true,
    })
  ).toBeVisible();
});


test('LOG-01 - Đăng nhập User bằng thông tin hợp lệ', async ({ page }) => {
  // Test data
  const email = 'nguyenvana@gmail.com';
  const password = 'qwe123!@#';
  const username = 'Nguyen Van A';

  // 1. Mở trang chủ
  await page.goto('/');

  // 2. Điều hướng đến trang đăng nhập
  await page.getByRole('link', { name: 'Đăng nhập' }).click();

  // 3. Nhập thông tin đăng nhập
  await page.getByRole('textbox', { name: 'Email' })
    .fill(email);

  await page.getByRole('textbox', { name: 'Mật khẩu' })
    .fill(password);

  // 4. Gửi yêu cầu đăng nhập
  await page.getByRole('button', { name: 'Đăng nhập' }).click();

  // 5. Xác nhận chuyển về trang chủ sau đăng nhập
  await expect(page).toHaveURL('/', {
    timeout: 15000,
  });

  // 6. Xác nhận trạng thái đã đăng nhập
  const profileLink = page
    .getByRole('navigation', { name: 'Điều hướng chính' })
    .getByRole('link', { name: 'Hồ sơ' });

  await expect(profileLink).toBeVisible();

  // 7. Truy cập Profile
  await profileLink.click();

  // 8. Xác nhận thông tin User
  await expect(
    page.getByRole('heading', {
      name: username,
      exact: true,
    })
  ).toBeVisible();
});


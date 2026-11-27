
import { test, expect, type Page } from '@playwright/test';
import { randomUUID } from 'node:crypto';

// Authentication tests luôn bắt đầu ở trạng thái Guest.
test.use({
  storageState: {
    cookies: [],
    origins: [],
  },
});

// ======================================================
// TEST DATA
// ======================================================

function getUser() {
  const email = process.env.E2E_USER_EMAIL;
  const password = process.env.E2E_USER_PASSWORD;

  if (!email || !password) {
    throw new Error('Missing E2E User credentials');
  }

  return { email, password };
}

function getModerator() {
  const email = process.env.E2E_MODERATOR_EMAIL;
  const password = process.env.E2E_MODERATOR_PASSWORD;

  if (!email || !password) {
    throw new Error('Missing E2E Moderator credentials');
  }

  return { email, password };
}

// ======================================================
// HELPERS
// ======================================================

async function openRegisterPage(page: Page) {
  await page.goto('/');

  await page.getByRole('link', { name: 'Đăng nhập' }).click();
  await page.getByRole('link', { name: 'Đăng ký' }).click();
}

async function openLoginPage(page: Page) {
  await page.goto('/');

  await page.getByRole('link', { name: 'Đăng nhập' }).click();
}

async function expectLoggedInAs(page: Page, email: string) {
  await expect(page).toHaveURL('/', {
    timeout: 15000,
  });

  const profileLink = page
    .getByRole('navigation', { name: 'Điều hướng chính' })
    .getByRole('link', { name: 'Hồ sơ' });

  await expect(profileLink).toBeVisible();

  await profileLink.click();

  const userEmail = page.getByTestId('user-email');

  await expect(userEmail).toBeVisible();
  await expect(userEmail).toHaveText(email);
}

async function expectLoginFailed(page: Page) {
  await expect(
    page.getByText(/tài khoản hoặc mật khẩu không chính xác/i)
  ).toBeVisible();

  await expect(page).toHaveURL(/\/login\/?$/);
}

// ======================================================
// REGISTRATION TESTS
// ======================================================

test('REG-01 - Đăng ký tài khoản với thông tin hợp lệ', async ({ page }) => {
  const username = `qa-${randomUUID()}`;
  const email = `${username}@example.com`;
  const password = getUser().password;

  await openRegisterPage(page);

  await page.getByRole('textbox', { name: 'Username' })
    .fill(username);

  await page.getByRole('textbox', { name: 'Email' })
    .fill(email);

  await page.getByRole('textbox', { name: 'Mật khẩu' })
    .fill(password);

  await page.getByRole('button', { name: 'Đăng ký' }).click();

  await expectLoggedInAs(page, email);
});

test('REG-02 - Đăng ký với email đã được sử dụng', async ({ page }) => {
  const user = getUser();

  await openRegisterPage(page);

  await page.getByRole('textbox', { name: 'Username' })
    .fill('Duplicate User');

  await page.getByRole('textbox', { name: 'Email' })
    .fill(user.email);

  await page.getByRole('textbox', { name: 'Mật khẩu' })
    .fill(user.password);

  await page.getByRole('button', { name: 'Đăng ký' }).click();

  await expect(page).toHaveURL(/\/register\/?$/);

  await expect(
    page.getByText(
      /email.*(đã tồn tại|đã được sử dụng|đã đăng ký)/i
    )
  ).toBeVisible({ timeout: 10000 });
});

test('REG-03 - Đăng ký với email sai định dạng', async ({ page }) => {
  await openRegisterPage(page);

  const email = page.getByRole('textbox', { name: 'Email' });

  await page.getByRole('textbox', { name: 'Username' })
    .fill('Invalid Email User');

  await email.fill('user-example.com');

  await page.getByRole('textbox', { name: 'Mật khẩu' })
    .fill(getUser().password);

  await page.getByRole('button', { name: 'Đăng ký' }).click();

  const isValid = await email.evaluate(
    (element: HTMLInputElement) => element.checkValidity()
  );

  expect(isValid).toBe(false);

  await expect(page).toHaveURL(/\/register\/?$/);
});

test('REG-04 - Đăng ký với mật khẩu quá ngắn', async ({ page }) => {
  await openRegisterPage(page);

  await page.getByRole('textbox', { name: 'Username' })
    .fill('Weak Password User');

  await page.getByRole('textbox', { name: 'Email' })
    .fill(`weak-${randomUUID()}@example.com`);

  await page.getByRole('textbox', { name: 'Mật khẩu' })
    .fill('qwe123');

  await page.getByRole('button', { name: 'Đăng ký' }).click();

  await expect(page).toHaveURL(/\/register\/?$/);

  await expect(
    page.getByText(
      /mật khẩu.*(tối thiểu|ít nhất|8 ký tự)|tối thiểu 8 ký tự/i
    )
  ).toBeVisible();
});

test('REG-05 - Đăng ký khi bỏ trống Username', async ({ page }) => {
  await openRegisterPage(page);

  const username = page.getByRole('textbox', { name: 'Username' });

  await page.getByRole('textbox', { name: 'Email' })
    .fill(`empty-${randomUUID()}@example.com`);

  await page.getByRole('textbox', { name: 'Mật khẩu' })
    .fill(getUser().password);

  await page.getByRole('button', { name: 'Đăng ký' }).click();

  const isValid = await username.evaluate(
    (element: HTMLInputElement) => element.checkValidity()
  );

  expect(isValid).toBe(false);

  await expect(page).toHaveURL(/\/register\/?$/);
});

test('REG-06 - Đăng ký thành công sau khi sửa dữ liệu không hợp lệ', async ({ page }) => {
  await openRegisterPage(page);

  const username = `qa-${randomUUID()}`;
  const email = `${username}@example.com`;

  const usernameInput = page.getByRole('textbox', {
    name: 'Username',
  });

  await page.getByRole('textbox', { name: 'Email' })
    .fill(email);

  await page.getByRole('textbox', { name: 'Mật khẩu' })
    .fill(getUser().password);

  // Submit lần đầu khi Username bị bỏ trống.
  await page.getByRole('button', { name: 'Đăng ký' }).click();

  const isValid = await usernameInput.evaluate(
    (element: HTMLInputElement) => element.checkValidity()
  );

  expect(isValid).toBe(false);

  // Sửa dữ liệu và submit lại.
  await usernameInput.fill(username);

  await page.getByRole('button', { name: 'Đăng ký' }).click();

  await expectLoggedInAs(page, email);
});

// ======================================================
// LOGIN TESTS
// ======================================================

test('LOG-01 - Đăng nhập User bằng thông tin hợp lệ', async ({ page }) => {
  const user = getUser();

  await openLoginPage(page);

  await page.getByRole('textbox', { name: 'Email' })
    .fill(user.email);

  await page.getByRole('textbox', { name: 'Mật khẩu' })
    .fill(user.password);

  await page.getByRole('button', { name: 'Đăng nhập' }).click();

  await expectLoggedInAs(page, user.email);
});

test('LOG-02 - Đăng nhập Moderator bằng thông tin hợp lệ', async ({ page }) => {
  const moderator = getModerator();

  await openLoginPage(page);

  await page.getByRole('textbox', { name: 'Email' })
    .fill(moderator.email);

  await page.getByRole('textbox', { name: 'Mật khẩu' })
    .fill(moderator.password);

  await page.getByRole('button', { name: 'Đăng nhập' }).click();

  await expect(page).toHaveURL('/', {
    timeout: 15000,
  });

  const moderationLink = page.getByRole('link', {
    name: 'Kiểm duyệt',
  });

  await expect(moderationLink).toBeVisible();

  await moderationLink.click();
});

test('LOG-03 - Đăng nhập với mật khẩu sai', async ({ page }) => {
  const user = getUser();

  await openLoginPage(page);

  await page.getByRole('textbox', { name: 'Email' })
    .fill(user.email);

  await page.getByRole('textbox', { name: 'Mật khẩu' })
    .fill('wrong-password-123');

  await page.getByRole('button', { name: 'Đăng nhập' }).click();

  await expectLoginFailed(page);
});

test('LOG-04 - Đăng nhập với tài khoản không tồn tại', async ({ page }) => {
  await openLoginPage(page);

  const unknownEmail = `unknown-${randomUUID()}@example.com`;

  await page.getByRole('textbox', { name: 'Email' })
    .fill(unknownEmail);

  await page.getByRole('textbox', { name: 'Mật khẩu' })
    .fill('SomePassword123');

  await page.getByRole('button', { name: 'Đăng nhập' }).click();

  await expectLoginFailed(page);
});

test('LOG-05 - Đăng nhập khi bỏ trống trường thông tin', async ({ page }) => {
  const user = getUser();

  const missingFields = ['Email', 'Mật khẩu'] as const;

  for (const missingField of missingFields) {
    await openLoginPage(page);

    const email = page.getByRole('textbox', { name: 'Email' });
    const password = page.getByRole('textbox', { name: 'Mật khẩu' });

    if (missingField !== 'Email') {
      await email.fill(user.email);
    }

    if (missingField !== 'Mật khẩu') {
      await password.fill(user.password);
    }

    await page.getByRole('button', { name: 'Đăng nhập' }).click();

    const missingInput = missingField === 'Email'
      ? email
      : password;

    const isValid = await missingInput.evaluate(
      (element: HTMLInputElement) => element.checkValidity()
    );

    expect(isValid).toBe(false);

    await expect(page).toHaveURL(/\/login\/?$/);
  }
});

test('LOG-06 - Đăng nhập sau khi nhập sai rồi nhập lại đúng', async ({ page }) => {
  const user = getUser();

  await openLoginPage(page);

  const email = page.getByRole('textbox', { name: 'Email' });
  const password = page.getByRole('textbox', { name: 'Mật khẩu' });

  await email.fill(user.email);
  await password.fill('wrong-password-123');

  await page.getByRole('button', { name: 'Đăng nhập' }).click();

  await expectLoginFailed(page);

  // Nhập lại password chính xác.
  await password.fill(user.password);

  await page.getByRole('button', { name: 'Đăng nhập' }).click();

  await expectLoggedInAs(page, user.email);
});

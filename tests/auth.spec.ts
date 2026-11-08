import { test, expect } from '@playwright/test';
import { randomUUID } from 'node:crypto';

const EXISTING_USER = {
  username: 'Nguyen Van A',
  email: 'nguyenvana@gmail.com',
  password: 'qwe123!@#',
};

async function openRegisterPage(page) {
  await page.goto('/');

  await page.getByRole('link', { name: 'Đăng nhập' }).click();
  await page.getByRole('link', { name: 'Đăng ký' }).click();
}

async function openLoginPage(page) {
  await page.goto('/');

  await page.getByRole('link', { name: 'Đăng nhập' }).click();
}

async function expectLoggedInAs(page, username: string) {
  await expect(page).toHaveURL('/', {
    timeout: 15000,
  });

  const profileLink = page
    .getByRole('navigation', { name: 'Điều hướng chính' })
    .getByRole('link', { name: 'Hồ sơ' });

  await expect(profileLink).toBeVisible();

  await profileLink.click();

  await expect(
    page.getByRole('heading', {
      name: username,
      exact: true,
    })
  ).toBeVisible();
}

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

  // 4. Xác nhận đăng ký thành công và kiểm tra Profile
  await expectLoggedInAs(page, username);
});

test('REG-02 - Đăng ký với email đã được sử dụng', async ({ page }) => {
  await openRegisterPage(page);

  await page.getByRole('textbox', { name: 'Username' })
    .fill('Duplicate User');

  await page.getByRole('textbox', { name: 'Email' })
    .fill(EXISTING_USER.email);

  await page.getByRole('textbox', { name: 'Mật khẩu' })
    .fill(EXISTING_USER.password);

  await page.getByRole('button', { name: 'Đăng ký' }).click();

  // Không được chuyển về trang chủ
  await expect(page).toHaveURL(/\/register\/?$/);

  // Xác nhận thông báo email đã tồn tại
  await expect(
    page.getByText(/email.*(đã tồn tại|đã được sử dụng|đã đăng ký)/i)
  ).toBeVisible({ timeout: 10000 });
});

test('REG-03 - Đăng ký với email sai định dạng', async ({ page }) => {
  await openRegisterPage(page);

  const email = page.getByRole('textbox', { name: 'Email' });

  await page.getByRole('textbox', { name: 'Username' })
    .fill('Invalid Email User');

  await email.fill('user-example.com');

  await page.getByRole('textbox', { name: 'Mật khẩu' })
    .fill(EXISTING_USER.password);

  await page.getByRole('button', { name: 'Đăng ký' }).click();

  // Kiểm tra trình duyệt đánh giá email không hợp lệ
  const isValid = await email.evaluate(
    (element: HTMLInputElement) => element.checkValidity()
  );

  expect(isValid).toBe(false);

  // Không được đăng ký thành công
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

  // Xác nhận vẫn ở trang đăng ký
  await expect(page).toHaveURL(/\/register\/?$/);

  // Xác nhận lỗi liên quan đến mật khẩu
  await expect(
    page.getByText(/mật khẩu.*(tối thiểu|ít nhất|8 ký tự)|tối thiểu 8 ký tự/i)
  ).toBeVisible();
});

test('REG-05 - Đăng ký khi bỏ trống Username', async ({ page }) => {
  await openRegisterPage(page);

  const username = page.getByRole('textbox', { name: 'Username' });

  // Cố ý không nhập Username
  await page.getByRole('textbox', { name: 'Email' })
    .fill(`empty-${randomUUID()}@example.com`);

  await page.getByRole('textbox', { name: 'Mật khẩu' })
    .fill(EXISTING_USER.password);

  await page.getByRole('button', { name: 'Đăng ký' }).click();

  // Kiểm tra Username không hợp lệ
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
  const password = EXISTING_USER.password;

  const usernameInput = page.getByRole('textbox', { name: 'Username' });

  // 1. Nhập thông tin nhưng bỏ trống Username
  await page.getByRole('textbox', { name: 'Email' })
    .fill(email);

  await page.getByRole('textbox', { name: 'Mật khẩu' })
    .fill(password);

  // 2. Submit lần đầu
  await page.getByRole('button', { name: 'Đăng ký' }).click();

  const isValid = await usernameInput.evaluate(
    (element: HTMLInputElement) => element.checkValidity()
  );

  expect(isValid).toBe(false);

  // 3. Sửa Username
  await usernameInput.fill(username);

  // 4. Submit lần hai
  await page.getByRole('button', { name: 'Đăng ký' }).click();

  // 5. Xác nhận tài khoản được tạo thành công
  await expectLoggedInAs(page, username);
});

test('LOG-01 - Đăng nhập User bằng thông tin hợp lệ', async ({ page }) => {
  // Test data
  const { username, email, password } = EXISTING_USER;

  // 1. Mở trang đăng nhập
  await page.goto('/');

  await page.getByRole('link', { name: 'Đăng nhập' }).click();

  // 2. Nhập thông tin đăng nhập
  await page.getByRole('textbox', { name: 'Email' })
    .fill(email);

  await page.getByRole('textbox', { name: 'Mật khẩu' })
    .fill(password);

  // 3. Gửi yêu cầu đăng nhập
  await page.getByRole('button', { name: 'Đăng nhập' }).click();

  // 4. Xác nhận đăng nhập thành công và kiểm tra Profile
  await expectLoggedInAs(page, username);
});


test('LOG-02 - Đăng nhập Moderator bằng thông tin hợp lệ', async ({ page }) => {
  // Test data
  const email = process.env.E2E_MODERATOR_EMAIL;
  const password = process.env.E2E_MODERATOR_PASSWORD;

  if (!email || !password) {
    throw new Error('Missing Moderator test credentials in .env');
  }

  // 1. Mở trang đăng nhập
  await page.goto('/');

  await page.getByRole('link', { name: 'Đăng nhập' }).click();

  // 2. Nhập thông tin Moderator
  await page.getByRole('textbox', { name: 'Email' })
    .fill(email);

  await page.getByRole('textbox', { name: 'Mật khẩu' })
    .fill(password);

  // 3. Gửi yêu cầu đăng nhập
  await page.getByRole('button', { name: 'Đăng nhập' }).click();

  // 4. Xác nhận đăng nhập thành công
  await expect(page).toHaveURL('/', {
    timeout: 15000,
  });

  // 5. Xác nhận trạng thái đã đăng nhập
  const profileLink = page
    .getByRole('navigation', { name: 'Điều hướng chính' })
    .getByRole('link', { name: 'Hồ sơ' });

  await expect(profileLink).toBeVisible();

  // 6. Xác nhận quyền truy cập chức năng Moderator
  const moderationLink = page
    .getByRole('navigation', { name: 'Điều hướng chính' })
    .getByRole('link', { name: /kiểm duyệt/i });

  await expect(moderationLink).toBeVisible();

  // 7. Truy cập chức năng kiểm duyệt
  await moderationLink.click();

  // 8. Xác nhận trang kiểm duyệt được mở
  await expect(
    page.getByRole('heading', { name: /kiểm duyệt/i })
  ).toBeVisible();
});


test('LOG-03 - Đăng nhập với mật khẩu sai', async ({ page }) => {
  await openLoginPage(page);

  await page.getByRole('textbox', { name: 'Email' })
    .fill(EXISTING_USER.email);

  await page.getByRole('textbox', { name: 'Mật khẩu' })
    .fill('wrong-password-123');

  await page.getByRole('button', { name: 'Đăng nhập' }).click();

  // Xác nhận thông báo đăng nhập thất bại
  await expect(
    page.getByText(/tài khoản hoặc mật khẩu không chính xác/i)
  ).toBeVisible();

  // Không được chuyển về trang chủ
  await expect(page).toHaveURL(/\/login\/?$/);
});

test('LOG-04 - Đăng nhập với tài khoản không tồn tại', async ({ page }) => {
  await openLoginPage(page);

  const unknownEmail = `unknown-${randomUUID()}@example.com`;

  await page.getByRole('textbox', { name: 'Email' })
    .fill(unknownEmail);

  await page.getByRole('textbox', { name: 'Mật khẩu' })
    .fill('SomePassword123');

  await page.getByRole('button', { name: 'Đăng nhập' }).click();

  await expect(
    page.getByText(/tài khoản hoặc mật khẩu không chính xác/i)
  ).toBeVisible();

  await expect(page).toHaveURL(/\/login\/?$/);
});

test('LOG-05 - Đăng nhập khi bỏ trống trường thông tin', async ({ page }) => {
  const missingFields = ['Email', 'Mật khẩu'];

  for (const missingField of missingFields) {
    await openLoginPage(page);

    const email = page.getByRole('textbox', { name: 'Email' });
    const password = page.getByRole('textbox', { name: 'Mật khẩu' });

    // Trường còn lại được nhập dữ liệu hợp lệ
    if (missingField !== 'Email') {
      await email.fill(EXISTING_USER.email);
    }

    if (missingField !== 'Mật khẩu') {
      await password.fill(EXISTING_USER.password);
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
  await openLoginPage(page);

  const password = page.getByRole('textbox', { name: 'Mật khẩu' });

  // 1. Nhập email hợp lệ
  await page.getByRole('textbox', { name: 'Email' })
    .fill(EXISTING_USER.email);

  // 2. Nhập sai mật khẩu
  await password.fill('wrong-password-123');

  await page.getByRole('button', { name: 'Đăng nhập' }).click();

  // 3. Xác nhận đăng nhập thất bại
  await expect(
    page.getByText(/tài khoản hoặc mật khẩu không chính xác/i)
  ).toBeVisible();

  await expect(page).toHaveURL(/\/login\/?$/);

  // 4. Nhập lại mật khẩu đúng
  await password.fill(EXISTING_USER.password);

  // 5. Đăng nhập lần hai
  await page.getByRole('button', { name: 'Đăng nhập' }).click();

  // 6. Xác nhận đăng nhập thành công và thông tin Profile
  await expectLoggedInAs(page, EXISTING_USER.username);
});
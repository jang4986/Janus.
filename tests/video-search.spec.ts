
import { test, expect } from '@playwright/test';
import { randomUUID } from 'node:crypto';

// Các test video bắt đầu ở trạng thái Guest.
// Nếu ứng dụng yêu cầu đăng nhập để xem video,
// hãy bỏ test.use này để sử dụng User storageState.
test.use({
  storageState: {
    cookies: [],
    origins: [],
  },
});

// ======================================================
// TEST DATA
// ======================================================

function requiredEnv(name: string): string {
  const value = process.env[name];

  if (!value) {
    throw new Error(`Missing environment variable: ${name}`);
  }

  return value;
}

const VIDEO_1_TITLE = requiredEnv('E2E_VIDEO_01_TITLE');
const VIDEO_2_TITLE = requiredEnv('E2E_VIDEO_02_TITLE');

const PARTIAL_KEYWORD = VIDEO_1_TITLE.slice(0, 3);
const NON_EXISTENT_KEYWORD = `video-not-found-${randomUUID()}`;

// ======================================================
// HELPERS
// ======================================================

async function searchVideo(page, keyword: string) {
  await page.goto('/');

  const searchbox = page.getByRole('searchbox', {
    name: 'Tìm video hoặc nhãn',
  });

  await searchbox.fill(keyword);
  await searchbox.press('Enter');
}

function getVideoResult(page, title: string) {
  return page.getByRole('button').filter({
    hasText: title,
  });
}

async function openVideoFromSearch(page, title: string) {
  await searchVideo(page, title);

  const videoResult = getVideoResult(page, title);

  await expect(videoResult).toBeVisible();

  await videoResult.click();
}

// ======================================================
// VID-01: Exact title search
// ======================================================

test('VID-01 - Tìm kiếm video theo tên chính xác', async ({ page }) => {
  await searchVideo(page, VIDEO_1_TITLE);

  const videoResult = getVideoResult(page, VIDEO_1_TITLE);

  await expect(videoResult).toHaveCount(1);
  await expect(videoResult).toBeVisible();
});

// ======================================================
// VID-02: Partial title search
// ======================================================

test('VID-02 - Tìm kiếm video theo một phần tên', async ({ page }) => {
  // 1. Tìm kiếm bằng một phần tên Video 01
  await searchVideo(page, PARTIAL_KEYWORD);

  // 2. Lấy kết quả tương ứng với hai video
  const result1 = getVideoResult(page, VIDEO_1_TITLE);
  const result2 = getVideoResult(page, VIDEO_2_TITLE);

  // 3. Video 01 phải xuất hiện
  await expect(result1).toBeVisible();

  // 4. Video 02 không chứa từ khóa nên không xuất hiện
  await expect(result2).toHaveCount(0);
});

// ======================================================
// VID-03: No results
// ======================================================

test('VID-03 - Tìm kiếm video không tồn tại', async ({ page }) => {
  await searchVideo(page, NON_EXISTENT_KEYWORD);

  await expect(
    page.getByText(
      `Không tìm thấy video phù hợp với “${NON_EXISTENT_KEYWORD}”.`,
      { exact: true }
    )
  ).toBeVisible();

  const videoResults = page.getByRole('button').filter({
    hasText: /\d+\s*lượt xem/i,
  });

  await expect(videoResults).toHaveCount(0);
});

// ======================================================
// VID-04: Open video
// ======================================================

test('VID-04 - Chọn video từ kết quả tìm kiếm', async ({ page }) => {
  await openVideoFromSearch(page, VIDEO_1_TITLE);

  await expect(page.locator('video').first()).toBeVisible();

  await expect(
    page.getByText(VIDEO_1_TITLE, { exact: true }).last()
  ).toBeVisible();
});

// ======================================================
// VID-05: Play video
// ======================================================

test('VID-05 - Phát video sau khi chọn từ kết quả tìm kiếm', async ({ page }) => {
  await openVideoFromSearch(page, VIDEO_1_TITLE);

  const video = page.locator('video').first();

  await expect(video).toBeVisible();

  // Chờ video có dữ liệu.
  // HAVE_CURRENT_DATA = 2.
  await expect.poll(
    () => video.evaluate(
      (element: HTMLVideoElement) => element.readyState
    ),
    { timeout: 20000 }
  ).toBeGreaterThanOrEqual(2);

  const initialTime = await video.evaluate(
    (element: HTMLVideoElement) => element.currentTime
  );

  // Xác nhận thời gian phát tăng.
  await expect.poll(
    () => video.evaluate(
      (element: HTMLVideoElement) => element.currentTime
    ),
    { timeout: 15000 }
  ).toBeGreaterThan(initialTime);
});

// ======================================================
// VID-06: Next video in Feed
// ======================================================

test('VID-06 - Chuyển sang video tiếp theo khi đang xem', async ({ page }) => {
  await page.goto('/');

  const feed = page.locator('.feed');
  const slides = feed.locator('.slide-video-frame');

  await expect(feed).toBeVisible();

  // Database E2E được seed đúng hai video.
  await expect(slides).toHaveCount(2);

  const firstSlide = slides.nth(0);
  const nextSlide = slides.nth(1);

  const firstVideo = firstSlide.locator('video');
  const nextVideo = nextSlide.locator('video');

  await expect(firstVideo).toBeVisible();
  await expect(nextSlide).toBeAttached();

  // Chờ video đầu tiên tải dữ liệu.
  await expect.poll(
    () => firstVideo.evaluate(
      (element: HTMLVideoElement) => element.readyState
    ),
    { timeout: 20000 }
  ).toBeGreaterThanOrEqual(2);

  const initialSource = await firstVideo.evaluate(
    (element: HTMLVideoElement) => element.currentSrc
  );

  expect(initialSource).not.toBe('');

  const initialScrollTop = await feed.evaluate(
    (element) => element.scrollTop
  );

  // Đưa chuột vào Feed.
  const feedBox = await feed.boundingBox();

  if (!feedBox) {
    throw new Error('Feed is not visible');
  }

  await page.mouse.move(
    feedBox.x + feedBox.width / 2,
    feedBox.y + feedBox.height / 2
  );

  // Cuộn xuống.
  await page.mouse.wheel(0, 700);

  await expect.poll(
    () => feed.evaluate(
      (element) => element.scrollTop
    ),
    { timeout: 10000 }
  ).toBeGreaterThan(initialScrollTop);

  // Video thứ hai chiếm hơn 80% vùng hiển thị.
  await expect.poll(
    () => nextSlide.evaluate((slide) => {
      const feedElement = slide.closest('.feed');

      if (!feedElement) return 0;

      const feedRect = feedElement.getBoundingClientRect();
      const slideRect = slide.getBoundingClientRect();

      if (slideRect.height === 0) return 0;

      const visibleTop = Math.max(
        feedRect.top,
        slideRect.top
      );

      const visibleBottom = Math.min(
        feedRect.bottom,
        slideRect.bottom
      );

      const visibleHeight = Math.max(
        0,
        visibleBottom - visibleTop
      );

      return visibleHeight / slideRect.height;
    }),
    { timeout: 10000 }
  ).toBeGreaterThan(0.8);

  // Chờ nguồn video tiếp theo xuất hiện.
  await expect.poll(
    () => nextVideo.evaluate(
      (element: HTMLVideoElement) => element.currentSrc
    ),
    { timeout: 15000 }
  ).not.toBe('');

  const nextSource = await nextVideo.evaluate(
    (element: HTMLVideoElement) => element.currentSrc
  );

  expect(nextSource).not.toBe(initialSource);

  // Xác nhận video thứ hai đã tải dữ liệu.
  await expect.poll(
    () => nextVideo.evaluate(
      (element: HTMLVideoElement) => element.readyState
    ),
    { timeout: 20000 }
  ).toBeGreaterThanOrEqual(2);
});

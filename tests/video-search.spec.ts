
import { test, expect } from '@playwright/test';
import { randomUUID } from 'node:crypto';

// Test data
const VIDEO_TITLE = 'Coi gì hài hài này :> Hahaha';
const PARTIAL_KEYWORD = 'Hài';
const NON_EXISTENT_KEYWORD = `video-not-found-${randomUUID()}`;

// Helper: Tìm kiếm video
async function searchVideo(page, keyword: string) {
  await page.goto('/');

  const searchbox = page.getByRole('searchbox', {
    name: 'Tìm video hoặc nhãn',
  });

  await searchbox.fill(keyword);
  await searchbox.press('Enter');
}

// Helper: Lấy video từ kết quả tìm kiếm
function getVideoResult(page, title: string) {
  return page.getByRole('button').filter({
    hasText: title,
  });
}

// Helper: Tìm kiếm và mở video
async function openVideoFromSearch(page, title: string) {
  await searchVideo(page, title);

  const videoResult = getVideoResult(page, title);

  await expect(videoResult).toBeVisible();

  await videoResult.click();
}


// ======================================================
// VID-01: Tìm kiếm video theo tên chính xác
// ======================================================

test('VID-01 - Tìm kiếm video theo tên chính xác', async ({ page }) => {
  // 1. Tìm kiếm video bằng tên chính xác
  await searchVideo(page, VIDEO_TITLE);

  // 2. Xác nhận chỉ tìm được video mong muốn
  const videoResult = getVideoResult(page, VIDEO_TITLE);

  await expect(videoResult).toHaveCount(1);
  await expect(videoResult).toBeVisible();
});

// ======================================================
// VID-02: Tìm kiếm video theo một phần tên
// ======================================================

test('VID-02 - Tìm kiếm video theo một phần tên', async ({ page }) => {
  // 1. Tìm kiếm bằng một phần tên video
  await searchVideo(page, PARTIAL_KEYWORD);

  // 2. Kiểm tra có video phù hợp với từ khóa
  const matchingResults = page.getByRole('button', {
    name: /Xem video:.*hài/i,
  });

  await expect(matchingResults.first()).toBeVisible();
});


// ======================================================
// VID-03: Tìm kiếm video không tồn tại
// ======================================================

test('VID-03 - Tìm kiếm video không tồn tại', async ({ page }) => {
  // 1. Tìm kiếm video không tồn tại
  await searchVideo(page, NON_EXISTENT_KEYWORD);

  // 2. Kiểm tra thông báo không tìm thấy kết quả
  await expect(
    page.getByText(
      `Không tìm thấy video phù hợp với “${NON_EXISTENT_KEYWORD}”.`,
      { exact: true }
    )
  ).toBeVisible();

  // 3. Xác nhận không có video trong kết quả tìm kiếm
  const videoResults = page.getByRole('button').filter({
    hasText: /\d+\s*lượt xem/i,
  });

  await expect(videoResults).toHaveCount(0);
});

// ======================================================
// VID-04: Chọn video từ kết quả tìm kiếm
// ======================================================

test('VID-04 - Chọn video từ kết quả tìm kiếm', async ({ page }) => {
  // 1. Tìm kiếm và mở video
  await openVideoFromSearch(page, VIDEO_TITLE);

  // 2. Kiểm tra giao diện xem video đã mở
  await expect(page.locator('video').first()).toBeVisible();

  // 3. Kiểm tra thông tin video tương ứng
  await expect(
    page.getByText(VIDEO_TITLE, { exact: true }).last()
  ).toBeVisible();
});


// ======================================================
// VID-05: Phát video sau khi chọn từ kết quả tìm kiếm
// ======================================================

test('VID-05 - Phát video sau khi chọn từ kết quả tìm kiếm', async ({ page }) => {
  // 1. Tìm kiếm và mở video
  await openVideoFromSearch(page, VIDEO_TITLE);

  // 2. Lấy video player
  const video = page.locator('video').first();

  await expect(video).toBeVisible();

  // 3. Kiểm tra video đã tải được dữ liệu
  // HAVE_CURRENT_DATA = 2
  await expect.poll(
    () => video.evaluate(
      (element: HTMLVideoElement) => element.readyState
    ),
    { timeout: 20000 }
  ).toBeGreaterThanOrEqual(2);

  // 4. Kiểm tra video thực sự đang phát
  const initialTime = await video.evaluate(
    (element: HTMLVideoElement) => element.currentTime
  );

  await expect.poll(
    () => video.evaluate(
      (element: HTMLVideoElement) => element.currentTime
    ),
    { timeout: 15000 }
  ).toBeGreaterThan(initialTime);
});


// ======================================================
// VID-06: Chuyển sang video tiếp theo khi đang xem
// ======================================================
test('VID-06 - Chuyển sang video tiếp theo khi đang xem', async ({ page }) => {
  // 1. Mở Feed
  await page.goto('/');

  // 2. Xác định Feed và danh sách video
  const feed = page.locator('.feed');
  const slides = feed.locator('.slide-video-frame');

  await expect(feed).toBeVisible();

  // 3. Lấy video đầu tiên và video tiếp theo
  const firstVideo = slides.nth(0).locator('video');
  const nextSlide = slides.nth(1);
  const nextVideo = nextSlide.locator('video');

  await expect(firstVideo).toBeVisible();
  await expect(nextSlide).toBeAttached();

  // 4. Chờ video đầu tiên tải dữ liệu
  await expect.poll(
    () => firstVideo.evaluate(
      (element: HTMLVideoElement) => element.readyState
    ),
    { timeout: 20000 }
  ).toBeGreaterThanOrEqual(2);

  // 5. Lưu nguồn video đầu tiên
  const initialSource = await firstVideo.evaluate(
    (element: HTMLVideoElement) => element.currentSrc
  );

  expect(initialSource).not.toBe('');

  // 6. Lưu vị trí cuộn ban đầu
  const initialScrollTop = await feed.evaluate(
    (element) => element.scrollTop
  );

  // 7. Đưa chuột vào khu vực Feed
  const feedBox = await feed.boundingBox();

  if (!feedBox) {
    throw new Error('Feed is not visible');
  }

  await page.mouse.move(
    feedBox.x + feedBox.width / 2,
    feedBox.y + feedBox.height / 2
  );

  // 8. Cuộn xuống để chuyển video tiếp theo
  await page.mouse.wheel(0, 700);

  // 9. Xác nhận Feed đã cuộn
  await expect.poll(
    () => feed.evaluate(
      (element) => element.scrollTop
    ),
    { timeout: 10000 }
  ).toBeGreaterThan(initialScrollTop);

  // 10. Xác nhận video thứ hai chiếm phần lớn vùng hiển thị của Feed
  await expect.poll(
    () => nextSlide.evaluate((slide) => {
      const feed = slide.closest('.feed');

      if (!feed) return 0;

      const feedRect = feed.getBoundingClientRect();
      const slideRect = slide.getBoundingClientRect();

      const visibleTop = Math.max(feedRect.top, slideRect.top);
      const visibleBottom = Math.min(feedRect.bottom, slideRect.bottom);

      const visibleHeight = Math.max(
        0,
        visibleBottom - visibleTop
      );

      return visibleHeight / slideRect.height;
    }),
    { timeout: 10000 }
  ).toBeGreaterThan(0.8);

  // 11. Xác nhận video tiếp theo có nguồn khác video ban đầu
  const nextSource = await nextVideo.evaluate(
    (element: HTMLVideoElement) => element.currentSrc
  );

  expect(nextSource).not.toBe('');
  expect(nextSource).not.toBe(initialSource);

  // 12. Xác nhận video tiếp theo đã tải dữ liệu
  await expect.poll(
    () => nextVideo.evaluate(
      (element: HTMLVideoElement) => element.readyState
    ),
    { timeout: 20000 }
  ).toBeGreaterThanOrEqual(2);
});

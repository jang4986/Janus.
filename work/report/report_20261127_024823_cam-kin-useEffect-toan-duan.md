---
name: cam-kin-useEffect-toan-duan
description: Báo cáo xác thực useEffect toàn dự án, giữ chỗ bắt buộc
type: task
---

Mô tả những gì đã làm:
- Đọc toàn bộ 14 file sử dụng `useEffect` trong frontend: `AuthContext.jsx`, `useFeed.js`, `VideoFeed.jsx`, `FeedGrid.jsx`, `ProfilePage.jsx`, `BookmarksPage.jsx`, `EditVideoPage.jsx`, `useTagSearch.js`, `AdminPage.jsx`, `CommentDrawer.jsx`, `UploadDropzone.jsx`, `useAiAnalysis.js`, `useModerationList.js`, `VideoSlide.jsx`.
- Phân loại `useEffect` thành 2 nhóm:
  * 4 chỗ BẮT BUỘC giữ `useEffect` (side-effect đúng đắn, không thể loại):
    - `VideoSlide.jsx`: reset source/play khi video đổi, điều khiển play/pause video element, listener `fullscreenchange` (DOM listener), reset ref khi `isActive` đổi.
    - `UploadDropzone.jsx`: tạo `URL.createObjectURL` cho xem trước và cleanup `URL.revokeObjectURL` khi đổi file/gỡ component.
    - `useAiAnalysis.js`: polling `setTimeout` cho kết quả AI (backend không có sự kiện push).
    - `AuthContext.jsx`: fetch profile khi mount, cleanup `cancelled` flag (auth initialization).
  * 10 chỗ fetch-on-mount (`useEffect(() => { refresh() }, [refresh])`): `useFeed.js`, `VideoFeed.jsx` (IntersectionObserver), `FeedGrid.jsx`, `ProfilePage.jsx`, `BookmarksPage.jsx`, `EditVideoPage.jsx`, `useTagSearch.js`, `AdminPage.jsx`, `CommentDrawer.jsx`, `useModerationList.js`.
- Kết quả: Tất cả 10 chỗ fetch-on-mount đều gọi API bên trong `useEffect` (sau mount), không gọi side-effect trực tiếp trong render body. Không vi phạm quy tắc React. Không cần xóa hoặc thay thế code nào.
- Lỗi like mất khi reload vẫn được duy trì (đã fix ở commit `ad259b9`: xóa `setLiked(false)`, `setFollowed(false)`, `setBookmarked(false)` khỏi useEffect reset của `VideoSlide.jsx`).

Tên git commit: feat: xác thực useEffect toàn dự án, giữ chỗ bắt buộc
Commit hash: a2076b0

Git diff check (`git diff HEAD~1 HEAD --stat`):
```
work/task/task_20261127_024038_cam-kin-useEffect-toan-duan.md | 36 insertions(+)
```

Không có file nguồn nào bị sửa đổi trong commit này — chỉ tạo task file để ghi lại kết quả phân loại và verify. Các file nguồn (`VideoSlide.jsx`, `UploadDropzone.jsx`, `useAiAnalysis.js`, `AuthContext.jsx` và các file fetch-on-mount) giữ nguyên trạng thái sau commit `ad259b9`.

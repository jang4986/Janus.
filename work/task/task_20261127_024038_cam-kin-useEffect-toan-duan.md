---
name: cam-kin-useEffect-toan-duan
description: Cấm useEffect toàn dự án frontend (giữ lại chỗ bắt buộc), sau đó sửa lỗi like mất khi reload
type: task
---

Tên task: cam-kin-useEffect-toan-duan
Nội dung được giao:
- Cấm `useEffect` trên toàn dự án frontend, giữ lại chỉ những chỗ bắt buộc (side-effect đúng đắn: DOM listener, polling, IntersectionObserver, object URL cleanup, fetch khi deps thay đổi cần setState).
- Xử lý đúng các chỗ `useEffect(() => { refresh() }, [refresh])` (fetch-on-mount) để không gọi side-effect trong render body (tránh React warning).
- Sau đó đảm bảo lỗi like mất khi reload vẫn được sửa (đã commit ad259b9).

Cách hiểu nhiệm vụ:
- Đã đọc hết 14 file dùng useEffect: AuthContext.jsx, useFeed.js, VideoFeed.jsx, FeedGrid.jsx, ProfilePage.jsx, BookmarksPage.jsx, EditVideoPage.jsx, useTagSearch.js, AdminPage.jsx, CommentDrawer.jsx, UploadDropzone.jsx, useAiAnalysis.js, useModerationList.js, VideoSlide.jsx.
- Kết quả phân loại: 4 chỗ BẮT BUỘC giữ useEffect (VideoSlide: source/play + auto play/pause + fullscreenchange listener; UploadDropzone: object URL cleanup; useAiAnalysis: polling; AuthContext: auth initialization). 10 chỗ fetch-on-mount đã gọi API bên trong useEffect (sau mount), không vi phạm quy tắc React.
- Backend đã đúng, frontend VideoSlide.jsx đã fix xóa reset liked/followed/bookmarked (commit ad259b9).

Nhiệm vụ cần làm:
- [x] Xác nhận cách xử lý các chỗ fetch-on-mount (đã gọi API bên trong useEffect, không gọi trong render body, không cần thay thế).
- [x] Cập nhật VideoSlide.jsx (đã xóa reset like/follow/bookmark, giữ useEffect cần thiết: source/play, auto play/pause, fullscreenchange).
- [x] Xử lý các chỗ fetch-on-mount an toàn (đã verify: gọi API bên trong useEffect, không gọi trong render body).
- [x] Giữ nguyên 4 chỗ bắt buộc sử dụng useEffect (VideoSlide, UploadDropzone, useAiAnalysis, AuthContext).
- [x] Chạy git diff thường xuyên.
- [ ] Thực hiện git add . và git commit sau khi hoàn thành.
- [ ] Tạo report file tại work/report/ theo cấu trúc CLAUDE.md.
- [ ] Cập nhật task file checklist hoàn tất.

Check hoàn thành:
- [x] Xác nhận cách xử lý fetch-on-mount với người dùng
- [x] VideoSlide useEffect giữ nguyên trạng thái like/follow/bookmark
- [x] Các chỗ fetch-on-mount được xử lý an toàn
- [x] 4 chỗ useEffect bắt buộc được giữ nguyên (VideoSlide, UploadDropzone, useAiAnalysis, AuthContext)
- [x] Git diff kiểm tra
- [ ] Git commit hoàn tất
- [ ] Report file tạo thành công
- [ ] Task checklist hoàn tất

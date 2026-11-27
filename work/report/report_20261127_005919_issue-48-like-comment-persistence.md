---
name: issue-48-like-comment-persistence
description: Báo cáo sửa lỗi Like và Bình luận không lưu về database, mất đi khi tải lại trang
type: task
---

Mô tả những gì đã làm:
- Điều tra xác định root cause của issue #48: trạng thái like/bookmark/follow được khởi tạo cứng là `false` ở frontend (VideoSlide.jsx) và backend feed endpoint không trả về trạng thái tương tác của người dùng hiện tại, nên các trạng thái này bị mất khi tải lại trang.
- Cập nhật `backend/src/app/schemas/video.py`: thêm các trường `owner_id`, `is_liked`, `is_bookmarked`, `like_count`, `is_following` vào schema `FeedItem`.
- Cập nhật `backend/src/app/services/video_service.py`: thêm tham số `requester` vào `list_published_feed`, truy vấn trạng thái like/bookmark/follow của người dùng hiện tại và like_count cho từng video trong feed, gán vào các trường của `FeedItem`.
- Cập nhật `backend/src/app/api/v1/endpoints/videos.py`: thêm tham số `user: OptionalUser = None` vào endpoint `/feed` và truyền `requester=user` vào service.
- Cập nhật `frontend/src/features/videos/components/VideoSlide.jsx`: khởi tạo `liked/followed/bookmarked` từ dữ liệu backend (`video.is_liked`, `video.is_following && video.owner_id`, `video.is_bookmarked`) thay vì `false` cứng.
- Xác minh bình luận được tải lại sau khi tạo/xóa: `CommentDrawer` đã re-fetch bình luận trên mount qua `useEffect loadComments`, bình luận có thể được khôi phục.
- Thực hiện `git add .` và `git commit` tất cả thay đổi.
- Tạo report file tại `work/report/`.
- Cập nhật task file checklist hoàn tất.

Tên git commit: fix: synchronize like/bookmark/follow status from backend on reload
Commit hash: d161046

Git diff check (git diff HEAD~1 HEAD --stat):
```
backend/src/app/api/v1/endpoints/videos.py         |  3 +-
backend/src/app/schemas/video.py                   |  5 +++
backend/src/app/services/video_service.py          | 51 +++++++++++++++++++++-
frontend/src/features/videos/components/VideoSlide.jsx  |  6 +--
work/task/task_20261127_005458_issue-48-like-comment-persistence.md | 36 +++++++++++++++
5 files changed, 95 insertions(+), 6 deletions(-)
```

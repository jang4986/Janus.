---
name: issue-48-like-comment-persistence
description: Báo cáo sửa lỗi Like và Bình luận không lưu về database, mất đi khi tải lại trang (phần frontend)
type: task
---

Mô tả những gì đã làm:
- Xác định root cause ở frontend: `VideoSlide.jsx` khởi tạo `liked/followed/bookmarked` từ dữ liệu backend (video.is_liked, video.is_following, video.is_bookmarked) nhưng một `useEffect` sau đó reset các trạng thái này về `false` mỗi khi component mount hoặc khi `video.id`/`video.stream_url` thay đổi → trạng thái tương tác bị mất khi reload trang hoặc trượt video.
- Sửa `frontend/src/features/videos/components/VideoSlide.jsx`: xóa `setLiked(false)`, `setFollowed(false)`, `setBookmarked(false)` trong `useEffect` reset để giữ nguyên trạng thái like/follow/bookmark nhận từ backend.
- Backend đã đúng: `social_service.toggle_like` và `create_comment` gọi `db.commit()`; `list_published_feed` trả về `is_liked`, `is_bookmarked`, `is_following`, `like_count` qua `FeedItem`; `CommentDrawer` re-fetch bình luận trên mount.
- `FeedGrid.jsx` chỉ hiển thị `like_count` từ backend, không cần thay đổi trạng thái tương tác.
- Thực hiện `git add .` và `git commit` tất cả thay đổi.
- Tạo report file tại `work/report/`.
- Cập nhật task file checklist hoàn tất.

Tên git commit: fix: giữ nguyên trạng thái like/follow/bookmark từ backend khi reload trang
Commit hash: ad259b9

Git diff check (git diff HEAD~1 HEAD --stat):
```
frontend/src/features/videos/components/VideoSlide.jsx | 3 deletions(-)
```

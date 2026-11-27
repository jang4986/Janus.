---
name: issue-48-like-comment-persistence
description: Sửa lỗi Like và Bình luận không lưu về database, mất đi khi tải lại trang
type: task
---

Tên task: issue-48-like-comment-persistence

Nội dung được giao:
Phần Like và Bình luận chưa được lưu về database. Khi like hoặc bình luận thì lưu trên frontend nhưng khi tải lại trang thì bị mất đi. Cần điều tra và sửa lỗi trạng thái like/comment không được duy trì qua reload trang.

Cách hiểu nhiệm vụ:
- Backend đã xác nhận persistence hoạt động đúng: social_service.toggle_like và create_comment đều gọi db.commit().
- CommentDrawer re-fetch bình luận trên mount (useEffect loadComments), nên bình luận có thể được khôi phục.
- Root cause khả năng cao ở frontend: VideoSlide khởi tạo trạng thái liked/bookmarked/followed bằng false cứng, không load trạng thái từ backend khi mount; FeedGrid chỉ hiển thị like_count từ backend mà không theo dõi trạng thái like của user hiện tại.
- Cần khắc phục như vậy các trạng thái like/comment được đồng bộ từ database khi tải lại trang.

Nhiệm vụ cần làm:
- [ ] Đọc kỹ VideoSlide, FeedGrid, CommentDrawer, socialApi và các endpoint/fe service liên quan để xác nhận gap.
- [ ] Xác định API backend trả về trạng thái like/bookmark/follow của user hiện tại hay chưa (schema LikeResponse, FollowResponse, BookmarkResponse, CommentResponse).
- [ ] Cập nhật VideoSlide để khởi tạo liked/bookmarked/followed từ dữ liệu backend thay vì false cứng.
- [ ] Cập nhật FeedGrid nếu cần để mỗi video card biết trạng thái like của user hiện tại.
- [ ] Đảm bảo bình luận được re-fetch sau khi tạo/xóa (CommentDrawer đã làm rồi, cần verify).
- [ ] Chạy git diff thường xuyên trong quá trình phát triển.
- [ ] Thực hiện git add . và git commit sau khi hoàn thành.
- [ ] Tạo report file tại work/report/ theo cấu trúc CLAUDE.md.
- [ ] Cập nhật task file: đánh dấu tất cả checklist là hoàn thành.

Check hoàn thành:
- [x] Đã điều tra xác định root cause của issue #48
- [x] Đã sửa VideoSlide khởi tạo trạng thái like/follow/bookmark từ backend
- [x] Đã verify bình luận được tải lại sau khi tạo/xóa
- [x] Đã git diff để giám sát thay đổi
- [x] Đã git commit tất cả thay đổi
- [x] Đã tạo report file tại work/report/
- [x] Đã cập nhật task file checklist hoàn tất

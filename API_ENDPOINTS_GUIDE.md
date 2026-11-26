# PBL6 Backend API — Endpoint and Request Guide

Tài liệu này được đối chiếu với FastAPI application hiện tại, Pydantic schemas,
dependencies, OpenAPI runtime tại `http://127.0.0.1:8000/openapi.json` và các
test Pytest/Newman local. Đây là tài liệu cho Backend; không phải tài liệu URL
Frontend hay kết nối trực tiếp đến PostgreSQL.

## 1. Thông tin chung

- Base URL local: `http://127.0.0.1:8000`
- API prefix: `/api/v1`
- Backend: FastAPI
- Authentication: JWT Bearer token
- Token hết hạn theo `ACCESS_TOKEN_EXPIRE_MINUTES`, mặc định trong code là 30 phút.
- Role hợp lệ: `user`, `moderator`, `admin`.
- Video chỉ nhận MP4, tối đa 50 MiB; storage hỗ trợ local và S3-compatible
  Cloudflare R2.
- AI background có thể chạy NSFW-Detection thật theo `AI_ANALYSIS_MODE`; khi
  xử lý video cũng trích xuất thumbnail JPEG vào storage.
- Không có endpoint logout, refresh token hoặc password reset. Admin
  user-management và endpoint phát video (`GET /api/v1/videos/{video_id}/stream`)
  đã tồn tại, mô tả lần lượt ở mục 3.15–3.19 và 3.20.

### Trạng thái xác minh

- **Đã test**: đã có request thực tế trong collection Newman hoặc test Pytest.
- **Code/OpenAPI**: route và schema đã được đối chiếu, nhưng chưa có request
  runtime riêng chứng minh đầy đủ hành vi đó.
- Không coi route Code/OpenAPI là bằng chứng nghiệp vụ đầy đủ.

## 2. Quy tắc request chung

### JWT

Đăng nhập bằng `POST /api/v1/auth/login`, lấy trường `access_token`, sau đó gửi:

```http
Authorization: Bearer <access_token>
```

Token được ký HS256, chứa `sub`, `role` và `exp`. Backend tra cứu user theo
`sub` và kiểm tra `is_active`. Token không hợp lệ, thiếu, hết hạn hoặc user
không còn hợp lệ trả HTTP `401`.

Không có cơ chế logout/revoke token hoặc refresh token trong code hiện tại.

### Lỗi validation

FastAPI/Pydantic trả HTTP `422` khi JSON, UUID, file field hoặc validation
không hợp lệ. Lỗi nghiệp vụ dùng JSON dạng:

```json
{
  "detail": "Thông báo lỗi"
}
```

### Upload file

Trong Postman chọn **Body → form-data**, tạo field `file`, đổi type của field
thành **File**, rồi chọn file MP4. Không tự đặt `Content-Type` khi dùng
multipart; Postman phải tự thêm boundary. `caption` là query parameter, không
phải multipart field:

```text
POST /api/v1/videos?caption=My%20caption
```

## 3. Endpoint chi tiết

### 3.1 Health check

**Thông tin chung**

- Method: `GET`
- Path: `/health`
- Operation ID: `health`
- Full URL mẫu: `http://127.0.0.1:8000/health`
- Chức năng: kiểm tra Backend còn phản hồi.
- Module: System
- Authentication: Không yêu cầu
- Role/permission: Không có
- Content-Type: Không có request body
- Trạng thái xác minh: **Đã test** — health trả HTTP `200`.

**A. Path parameters**: Không có.

**B. Query parameters**: Không có.

**C. Headers**: Không bắt buộc.

**D. Request body**: Không có.

**E. Response mẫu**

```json
{"status": "ok"}
```

HTTP `200`.

**F. Lỗi thường gặp**

- Không kết nối được: Backend chưa chạy, sai host/port hoặc firewall.
- HTTP `5xx`: lỗi khởi động/runtime; không có response nghiệp vụ riêng được
  định nghĩa trong endpoint.

**G. Ví dụ gọi API**

```bash
curl http://127.0.0.1:8000/health
```

### 3.2 Đăng ký tài khoản

**Thông tin chung**

- Method: `POST`
- Path: `/api/v1/auth/register`
- Operation ID: `register`
- Full URL mẫu: `http://127.0.0.1:8000/api/v1/auth/register`
- Chức năng: tạo user mới.
- Module: Auth
- Authentication: Không yêu cầu
- Role/permission: User mới mặc định có role `user`.
- Content-Type: `application/json`
- Trạng thái xác minh: **Đã test** — Auth Newman trả `201`; duplicate trả `409`.

**A. Path parameters**: Không có.

**B. Query parameters**: Không có.

**C. Headers**

```http
Content-Type: application/json
```

**D. Request body**

```json
{
  "email": "user@example.com",
  "display_name": "Example User",
  "password": "password123"
}
```

| Trường | Kiểu | Bắt buộc | Quy tắc |
|---|---|---:|---|
| `email` | string/email | Có | Email hợp lệ; lưu dạng lowercase |
| `display_name` | string | Có | 1–120 ký tự |
| `password` | string | Có | 8–128 ký tự |

**E. Response mẫu**

```json
{
  "id": "00000000-0000-0000-0000-000000000001",
  "email": "user@example.com",
  "display_name": "Example User",
  "role": "user"
}
```

HTTP `201`.

**F. Lỗi thường gặp**

- `409`: email đã được sử dụng.
- `422`: email, display name hoặc password không đúng schema.
- `5xx`: database không khả dụng hoặc lỗi commit.

**G. Ví dụ gọi API**

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/register ^
  -H "Content-Type: application/json" ^
  -d "{\"email\":\"user@example.com\",\"display_name\":\"Example User\",\"password\":\"password123\"}"
```

### 3.3 Đăng nhập

**Thông tin chung**

- Method: `POST`
- Path: `/api/v1/auth/login`
- Operation ID: `login`
- Full URL mẫu: `http://127.0.0.1:8000/api/v1/auth/login`
- Chức năng: xác thực email/password và cấp access token.
- Module: Auth
- Authentication: Không yêu cầu
- Role/permission: Không có
- Content-Type: `application/json`
- Trạng thái xác minh: **Đã test** — Auth/Newman login trả `200`.

**A. Path parameters**: Không có.

**B. Query parameters**: Không có.

**C. Headers**

```http
Content-Type: application/json
```

**D. Request body**

```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

| Trường | Kiểu | Bắt buộc | Quy tắc |
|---|---|---:|---|
| `email` | string/email | Có | Email hợp lệ |
| `password` | string | Có | Không có min/max riêng trong `LoginRequest` |

**E. Response mẫu**

```json
{
  "access_token": "<access_token_from_this_response>",
<<<<<<< HEAD
  "token_type": "bearer"
=======
  "token_type": "bearer",
  "refresh_token": "<refresh_token_from_this_response>"
>>>>>>> 0dcf2c46a0f557080b0fcca8ac5384151d871ffd
}
```

HTTP `200`. Không ghi token thật vào tài liệu hoặc source control.

**F. Lỗi thường gặp**

- `401`: email không tồn tại hoặc password sai.
- `422`: email sai định dạng hoặc thiếu field.

**G. Ví dụ gọi API**

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/login ^
  -H "Content-Type: application/json" ^
  -d "{\"email\":\"user@example.com\",\"password\":\"password123\"}"
```

Trong Postman lưu `access_token` từ response vào collection/environment
variable, không hardcode token đã hết hạn.

### 3.4 Xem hồ sơ hiện tại

**Thông tin chung**

- Method: `GET`
- Path: `/api/v1/profile`
- Operation ID: `profile`
- Full URL mẫu: `http://127.0.0.1:8000/api/v1/profile`
- Chức năng: trả user của JWT hiện tại.
- Module: User Profile
- Authentication: Bắt buộc Bearer JWT
- Role/permission: User active; mọi role hợp lệ đều được gọi.
- Content-Type: Không có body
- Trạng thái xác minh: **Đã test** — User Profile collection.

**A/B. Path và query parameters**: Không có.

**C. Headers**

```http
Authorization: Bearer <access_token>
```

**D. Request body**: Không có.

**E. Response mẫu**

```json
{
  "id": "00000000-0000-0000-0000-000000000001",
  "email": "user@example.com",
  "display_name": "Example User",
  "role": "user"
}
```

HTTP `200`.

**F. Lỗi thường gặp**

- `401`: thiếu, sai, hết hạn hoặc không xác thực được JWT.

**G. Ví dụ gọi API**

```bash
curl http://127.0.0.1:8000/api/v1/profile ^
  -H "Authorization: Bearer <access_token>"
```

### 3.5 Upload video

**Thông tin chung**

- Method: `POST`
- Path: `/api/v1/videos`
- Operation ID: `upload_video`
- Full URL mẫu: `http://127.0.0.1:8000/api/v1/videos?caption=Demo`
- Chức năng: lưu video qua storage driver (R2 hoặc local), tạo AI job và trả
  metadata video.
- Module: Video Upload
- Authentication: Bắt buộc Bearer JWT
- Role/permission: User active; không yêu cầu moderator/admin.
- Content-Type: `multipart/form-data`
- Trạng thái xác minh: **Đã test** — video thật, Pytest và Newman.

**A. Path parameters**: Không có.

**B. Query parameters**

| Tham số | Kiểu | Bắt buộc | Mặc định | Ý nghĩa |
|---|---|---:|---|---|
| `caption` | string hoặc null | Không | `null` | Caption video; truyền trên URL |

**C. Headers**

```http
Authorization: Bearer <access_token>
```

Không tự thêm `Content-Type`; client tạo multipart boundary.

**D. Request body**

Body → form-data:

| Field | Type | Bắt buộc | Quy tắc |
|---|---|---:|---|
| `file` | File | Có | Tên file `.mp4`, MIME `video/mp4`, MP4 magic bytes/brand/codec hợp lệ |

Giới hạn kích thước là 50 MiB (`50 * 1024 * 1024`). Backend kiểm tra marker
codec `avc1`, `hvc1`, `hev1`, `av01` hoặc `mp4v`.

**E. Response mẫu**

```json
{
  "id": "00000000-0000-0000-0000-000000000002",
  "original_filename": "Travel_4.mp4",
  "caption": "Demo",
  "size_bytes": 2609079,
  "status": "processing",
  "created_at": "2026-10-25T15:00:00Z"
}
```

HTTP `201`. Background analysis có thể chuyển status thành `published` nếu an toàn hoặc
`pending_review` nếu phát hiện vi phạm. Thumbnail được lưu theo key
`thumbnails/<video_id>.jpg`.

**F. Lỗi thường gặp**

- `400`: không phải `.mp4`, MIME khác `video/mp4`, magic bytes/brand/codec không
  hợp lệ.
- `401`: thiếu hoặc sai JWT.
- `413`: vượt quá 50 MiB.
- `422`: thiếu field file hoặc request multipart sai.
- `5xx`: lỗi lưu file/database.

**G. Ví dụ gọi API**

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/videos?caption=Demo" ^
  -H "Authorization: Bearer <access_token>" ^
  -F "file=@local/TestDataset-v2/Adult/Adult (1).mp4;type=video/mp4"
```

### 3.6 Liệt kê video của tôi

**Thông tin chung**

- Method: `GET`
- Path: `/api/v1/videos`
- Operation ID: `list_my_videos`
- Full URL mẫu: `http://127.0.0.1:8000/api/v1/videos`
- Chức năng: liệt kê video chưa bị soft-delete của user hiện tại.
- Module: Video Management
- Authentication: Bắt buộc Bearer JWT
- Role/permission: Chỉ video thuộc user trong token.
- Content-Type: Không có body
- Trạng thái xác minh: **Đã test** — Video Management collection.

**A/B. Path và query parameters**: Không có. Chưa có pagination/search/filter.

**C. Headers**

```http
Authorization: Bearer <access_token>
```

**D. Request body**: Không có.

**E. Response mẫu**

```json
[
  {
    "id": "00000000-0000-0000-0000-000000000002",
    "original_filename": "Travel_4.mp4",
    "caption": null,
    "size_bytes": 2609079,
    "status": "published",
    "created_at": "2026-10-25T15:00:00Z",
    "owner_name": "Traveler"
  }
]
```

HTTP `200`; có thể là `[]`.

- `owner_name`: tên hiển thị của chủ video (dùng cho feed); nullable.

**F. Lỗi thường gặp**: `401` khi thiếu/sai JWT.

**G. Ví dụ gọi API**

```bash
curl http://127.0.0.1:8000/api/v1/videos ^
  -H "Authorization: Bearer <access_token>"
```

### 3.7 Public feed

**Thông tin chung**

- Method: `GET`
- Path: `/api/v1/feed`
- Operation ID: `feed`
<<<<<<< HEAD
- Full URL mẫu: `http://127.0.0.1:8000/api/v1/feed`
- Chức năng: cursor pagination các video `published`, `public`, chưa bị xóa.
=======
- Full URL mẫu: `http://127.0.0.1:8000/api/v1/feed?limit=8`
- Chức năng: Phân trang con trỏ (cursor pagination) danh sách video `published`, `public`, chưa bị xóa phục vụ giao diện xem video ngắn cuộn dọc.
>>>>>>> 0dcf2c46a0f557080b0fcca8ac5384151d871ffd
- Module: Video Management
- Authentication: Không yêu cầu
- Role/permission: Không có
- Content-Type: Không có body
<<<<<<< HEAD
- Trạng thái xác minh: **Đã test** — Video Management collection.

**A/B. Path và query parameters**

| Tham số | Kiểu | Bắt buộc | Mặc định | Quy tắc |
|---|---|---:|---:|---|
| `limit` | integer | Không | `8` | `1..20`; backend lấy `limit + 1` để tính `has_more` |
| `cursor` | ISO datetime/null | Không | `null` | Chỉ lấy video có `created_at` nhỏ hơn cursor |
=======
- Trạng thái xác minh: **Đã test** — Video Management collection & Pytest.

**A/B. Path và query parameters**

| Tham số | Kiểu | Bắt buộc | Mặc định | Quy tắc & Hợp đồng API |
|---|---|---:|---:|---|
| `limit` | integer | Không | `8` | Giới hạn từ `1..20`. Hỗ trợ gọi các batch nhỏ (ví dụ `limit=2` hoặc `limit=3`) để tối ưu hóa sliding window (cửa sổ trượt DOM 3 phần tử) ở Frontend. Backend truy vấn `limit + 1` bản ghi để xác định cờ `has_more`. |
| `cursor` | ISO datetime/null | Không | `null` | Chỉ lấy các video có thời gian `created_at` nhỏ hơn cursor (sắp xếp giảm dần theo thời gian tạo). |
>>>>>>> 0dcf2c46a0f557080b0fcca8ac5384151d871ffd

**C. Headers**: Không bắt buộc.

**D. Request body**: Không có.

**E. Response mẫu**

```json
{
  "items": [
    {
      "id": "00000000-0000-0000-0000-000000000002",
<<<<<<< HEAD
      "caption": "Demo",
=======
      "caption": "Màn vũ đạo sôi động",
>>>>>>> 0dcf2c46a0f557080b0fcca8ac5384151d871ffd
      "stream_url": "https://pub-example.r2.dev/videos/<video_id>.mp4",
      "thumbnail_url": "https://pub-example.r2.dev/thumbnails/<video_id>.jpg",
      "allow_comments": true,
      "created_at": "2026-11-01T15:00:00Z"
    }
  ],
  "has_more": true,
  "next_cursor": "2026-11-01T15:00:00Z"
}
```

<<<<<<< HEAD
`thumbnail_url` có thể là `null` nếu thumbnail chưa tồn tại. `stream_url`
trỏ trực tiếp tới CDN R2 khi dùng S3 storage và hỗ trợ Range Request. HTTP
`200`; `items` có thể là `[]`.

Frontend phải đọc `response.items` trước khi gọi `.map()` và dùng trực tiếp
`item.stream_url`; không tự ghép `/api/v1/videos/{video_id}/stream` cho Feed.

**F. Lỗi thường gặp**: lỗi kết nối database có thể gây `5xx`; không có lỗi
nghiệp vụ riêng trong endpoint. `422` nếu `limit` ngoài `1..20` hoặc cursor
không đúng định dạng.
=======
**Quy ước phân trang hữu hạn & Vòng lặp Client (Finite Pagination & Client Loop Contract):**
- **Tại Backend:** Cơ sở dữ liệu lưu trữ hữu hạn. Khi người dùng cuộn đến trang cuối cùng, Backend sẽ trả về `has_more: false` và `next_cursor: null`.
- **Hợp đồng với Frontend:** Khi nhận `has_more: false`, Frontend **tuyệt đối không được tiếp tục gửi request lên server** (tránh vòng lặp vô tận gây quá tải hạ tầng). Thay vào đó, Frontend sẽ duy trì danh sách video đã nạp vào client state và tự động quay vòng lại đầu danh sách (looping replay) để duy trì trải nghiệm lướt video ngắn vô tận như TikTok / YouTube Shorts.
- `stream_url`: Trỏ trực tiếp tới CDN R2 khi dùng S3 storage và hỗ trợ Range Request, hoặc fallback về endpoint stream cục bộ `/api/v1/videos/{video_id}/stream`.
- `thumbnail_url`: Có thể là `null` nếu thumbnail chưa được sinh xong.

**F. Lỗi thường gặp**: Lỗi kết nối database có thể gây `5xx`; không có lỗi nghiệp vụ riêng trong endpoint. Trả về `422 Unprocessable Entity` nếu `limit` ngoài khoảng `1..20` hoặc `cursor` không đúng định dạng ISO 8601.
>>>>>>> 0dcf2c46a0f557080b0fcca8ac5384151d871ffd

**G. Ví dụ gọi API**

```bash
<<<<<<< HEAD
curl http://127.0.0.1:8000/api/v1/feed
=======
curl http://127.0.0.1:8000/api/v1/feed?limit=8
>>>>>>> 0dcf2c46a0f557080b0fcca8ac5384151d871ffd
```

### 3.7.1 Tìm kiếm video theo tag — Grid View

**Thông tin chung**

- Method: `GET`
- Path: `/api/v1/videos/search`
- Alias: `/api/v1/search/videos-by-tag/grid`
- Full URL mẫu:
  `http://127.0.0.1:8000/api/v1/videos/search?tag=Safe&limit=12`
- Chức năng: tìm video theo label để hiển thị dạng grid.
- Authentication: Không yêu cầu.
- Trạng thái xác minh: **Đã test** — tag `Safe`, cursor pagination và CDN
  thumbnail.

**A/B. Query parameters**

| Tham số | Kiểu | Bắt buộc | Mặc định | Quy tắc |
|---|---|---:|---:|---|
| `tag` | string | Có | — | Không được rỗng; matching không phân biệt hoa thường |
| `limit` | integer | Không | `12` | `1..20` |
| `cursor` | ISO datetime/null | Không | `null` | Lọc `created_at < cursor` |

Chỉ video thỏa đồng thời `published`, `visibility=public` và
`is_deleted=false` được trả về.

**C. Response mẫu**

```json
{
  "items": [
    {
      "id": "00000000-0000-0000-0000-000000000002",
      "caption": "Demo",
      "thumbnail_url": "https://pub-example.r2.dev/thumbnails/<video_id>.jpg",
      "stream_url": "https://pub-example.r2.dev/videos/<video_id>.mp4",
      "like_count": 12,
      "author": {
        "id": "00000000-0000-0000-0000-000000000001",
        "username": "Example User#1234",
        "avatar_url": null
      },
      "matched_labels": ["Safe"],
      "created_at": "2026-11-01T15:00:00Z"
    }
  ],
  "has_more": false,
  "next_cursor": null
}
```

Grid nên chỉ render `thumbnail_url` (ví dụ 4 cột); chỉ tải/phát
`stream_url` khi người dùng mở video.

### 3.7.2 Chỉnh sửa video và quản lý nhãn (UC007)

#### PATCH `/api/v1/videos/{video_id}`

Owner có thể cập nhật caption, `visibility` (`public` hoặc `private`) và
`allow_comments` (boolean). Không thể thay đổi file gốc, view count, like
count hoặc audit data.

```json
{
  "caption": "Updated caption",
  "visibility": "private",
  "allow_comments": false
}
```

Video `is_deleted=true` trả `404`. Video `rejected` không được chuyển sang
`public` qua route này và trả `400`.

#### GET `/api/v1/videos/{video_id}/labels`

Trả danh sách label gồm `name`, `confidence`, `level` và `source` (`ai` hoặc
`user`).

#### POST `/api/v1/videos/{video_id}/labels/confirm`

Đây là path thực tế trong router; path `/confirm-labels` không được đăng ký.
Owner gửi:

```json
{"labels": ["travel", "vlog"]}
```

Label AI vi phạm nghiêm trọng (`Adult`, `level=HIGH`, `source=ai`) được bảo
toàn và không bị ghi đè hoặc xóa bởi danh sách user. Video vẫn ở
`pending_review`, kể cả khi owner xác nhận danh sách label khác.

#### Comment enforcement

`POST /api/v1/videos/{video_id}/comments` trả `403 Forbidden` khi
`allow_comments=false`. Tương tác với video soft-deleted trả `404`.

### 3.7.3 Thumbnail và storage

Frame đầu tiên (fallback khoảng `0.5s` nếu cần) được encode JPEG quality 85
qua OpenCV. Object key chuẩn hóa là `thumbnails/<video_id>.jpg`; video dùng
`videos/<video_id>.mp4`. `StorageService` hỗ trợ upload local/S3, tải video
vào temporary directory cho AI và tự dọn temporary file sau khi xử lý.

### 3.8 Xem kết quả AI của video

**Thông tin chung**

- Method: `GET`
- Path: `/api/v1/videos/{video_id}/ai`
- Operation ID: `ai_result`
- Full URL mẫu: `http://127.0.0.1:8000/api/v1/videos/<video_id>/ai`
<<<<<<< HEAD
- Chức năng: đọc AI job, transcript và labels.
=======
- Chức năng: Đọc tiến trình phân tích AI, transcript, nhãn kiểm duyệt và trạng thái cập nhật của video (hỗ trợ polling định kỳ 2 giây/lần ở client).
>>>>>>> 0dcf2c46a0f557080b0fcca8ac5384151d871ffd
- Module: AI Analysis
- Authentication: Bắt buộc Bearer JWT
- Role/permission: Owner, moderator hoặc admin.
- Content-Type: Không có body
<<<<<<< HEAD
- Trạng thái xác minh: **Đã test** — AI Analysis collection.
=======
- Trạng thái xác minh: **Đã test** — AI Analysis collection & Pytest integration.
>>>>>>> 0dcf2c46a0f557080b0fcca8ac5384151d871ffd

**A. Path parameters**

| Tham số | Kiểu | Bắt buộc | Ý nghĩa |
|---|---|---:|---|
<<<<<<< HEAD
| `video_id` | UUID | Có | ID video cần đọc |
=======
| `video_id` | UUID | Có | ID video cần kiểm tra kết quả phân tích AI |
>>>>>>> 0dcf2c46a0f557080b0fcca8ac5384151d871ffd

**B. Query parameters**: Không có.

**C. Headers**

```http
Authorization: Bearer <access_token>
```

**D. Request body**: Không có.

**E. Response mẫu**

<<<<<<< HEAD
Khi NSFW-Detection chạy thật và phát hiện vi phạm Adult (video chuyển
sang `pending_review`):
=======
Response Model: `AIResultResponse`

Khi NSFW-Detection phát hiện vi phạm nhạy cảm (Adult):
>>>>>>> 0dcf2c46a0f557080b0fcca8ac5384151d871ffd

```json
{
  "video_id": "00000000-0000-0000-0000-000000000002",
  "job_status": "succeeded",
<<<<<<< HEAD
  "transcript": "[NSFW-Detection] phán quyết: ADULT | độ tin cậy: 0.87 | anchor đã đánh giá: 12 | fps: 30.0\n[Speech-to-Text] chưa được triển khai — chưa có transcript âm thanh.",
  "labels": [
    {
      "name": "Adult",
      "confidence": 0.87,
      "level": "HIGH"
    }
  ]
}
```

Khi môi trường AI chưa sẵn sàng và `AI_ANALYSIS_MODE=auto`, job ghi rõ lý do
và dùng kết quả mock (đã xác minh runtime với Neon):

```json
{
  "video_id": "00000000-0000-0000-0000-000000000002",
  "job_status": "succeeded",
  "transcript": "[NSFW-Detection chưa sẵn sàng: chưa cài thư viện: tensorflow, torch, cv2, numpy]\nMock transcript for development testing.",
  "labels": [
    {
      "name": "Safe",
      "confidence": 0.95,
      "level": "HIGH"
    }
  ]
}
```

HTTP `200`. Với `AI_ANALYSIS_MODE=required` và môi trường AI chưa sẵn sàng,
`job_status` là `failed` và `job.error_message` chứa lý do.

**F. Lỗi thường gặp**

- `401`: thiếu/sai JWT.
- `404`: video không tồn tại, đã xóa hoặc không thuộc owner và caller không
  phải moderator/admin.
- `422`: `video_id` không phải UUID.
=======
  "transcript": "[NSFW-Detection] phán quyết: ADULT | độ tin cậy: 0.73 | anchor đã đánh giá: 25 | fps: 30.0\n[Speech-to-Text] chưa được triển khai — chưa có transcript âm thanh.\n[Chưa triển khai] violence: bộ nhận diện Violence chưa được triển khai\n[Chưa triển khai] sound: bộ nhận diện Sound/Audio chưa được triển khai\n[Chưa triển khai] text: bộ nhận diện Text (Speech-to-Text + Text Analysis) chưa được triển khai",
  "labels": [
    {
      "name": "Adult",
      "confidence": 0.7337,
      "level": "MEDIUM",
      "source": "ai"
    }
  ],
  "video_status": "rejected"
}
```

Khi video an toàn (Safe):

```json
{
  "video_id": "00000000-0000-0000-0000-000000000003",
  "job_status": "succeeded",
  "transcript": "[NSFW-Detection] phán quyết: NORMAL | độ tin cậy: 0.28 | anchor đã đánh giá: 30 | fps: 30.0",
  "labels": [
    {
      "name": "Safe",
      "confidence": 0.2844,
      "level": "LOW",
      "source": "ai"
    }
  ],
  "video_status": "published"
}
```

| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `video_id` | UUID | ID của video |
| `job_status` | string | Trạng thái tiến trình AI: `"pending"` (chờ), `"running"` (đang chạy), `"succeeded"` (thành công), `"failed"` (thất bại) |
| `transcript` | string/null | Chuỗi báo cáo chi tiết từ các module (thị giác, STT, các module mở rộng) |
| `labels` | list[LabelResponse] | Danh sách nhãn kiểm duyệt kèm `name`, `confidence` (0.0..1.0), `level` (`LOW`/`MEDIUM`/`HIGH`), `source` (`ai`/`manual`) |
| `video_status` | string/null | Trạng thái nghiệp vụ hiện tại của video: `"published"`, `"pending_review"`, `"rejected"`, `"processing"`, `"failed"` |

**Vòng đời trạng thái Video & Ma trận phán quyết tự động của AI:**

Sau khi tiến trình AI nền hoàn tất phân tích video, hệ thống tự động áp dụng ma trận phán quyết 3 trường hợp:
1. **Trường hợp 1 - VI PHẠM RÕ RÀNG (Adult / High Risk / Confidence >= 0.85):**
   - **Điều kiện:** Phát hiện nhãn `Adult` (không phân biệt chữ hoa/thường) HOẶC nhãn có `level == "HIGH"` HOẶC `confidence >= 0.85`.
   - **Cập nhật:** `video.status = "rejected"`.
   - **Hành động hệ thống:** Video bị loại bỏ hoàn toàn khỏi Feed công khai; tự động tạo bản ghi `ModerationReview` với lý do *"Tự động từ chối bởi hệ thống AI: Phát hiện nội dung vi phạm tiêu chuẩn (Adult)."*.
2. **Trường hợp 2 - RANH GIỚI NGHI VẤN (Borderline / Medium Risk):**
   - **Điều kiện:** Nhãn có `level == "MEDIUM"` HOẶC `0.4 <= confidence < 0.85` (đối với các nội dung nghi vấn nhưng chưa đủ ngưỡng tự động từ chối).
   - **Cập nhật:** `video.status = "pending_review"`.
   - **Hành động hệ thống:** Video tạm ẩn khỏi Feed công khai và chuyển vào Hàng đợi kiểm duyệt (Moderation Queue) chờ Moderator/Admin xem xét thủ công.
3. **Trường hợp 3 - NỘI DUNG AN TOÀN (Safe / Low Risk):**
   - **Điều kiện:** `report.is_safe` là `True` và không có bất kỳ nhãn rủi ro cao hoặc trung bình nào.
   - **Cập nhật:** `video.status = "published"`.
   - **Hành động hệ thống:** Tự động gắn nhãn `Safe` và xuất bản video ngay lập tức lên Feed công khai.

**F. Lỗi thường gặp**

- `401 Unauthorized`: Thiếu hoặc sai Bearer JWT token.
- `404 Not Found`: Video không tồn tại, đã bị xóa mềm, hoặc video thuộc người khác mà người gọi không có quyền moderator/admin.
- `422 Unprocessable Entity`: `video_id` không phải định dạng UUID hợp lệ.
>>>>>>> 0dcf2c46a0f557080b0fcca8ac5384151d871ffd

**G. Ví dụ gọi API**

```bash
curl http://127.0.0.1:8000/api/v1/videos/<video_id>/ai ^
  -H "Authorization: Bearer <access_token>"
```

### 3.9 Soft-delete video

**Thông tin chung**

- Method: `DELETE`
- Path: `/api/v1/videos/{video_id}`
- Operation ID: `delete_video`
- Full URL mẫu: `http://127.0.0.1:8000/api/v1/videos/<video_id>`
- Chức năng: đánh dấu video đã xóa, không xóa bản ghi ngay.
- Module: Video Management
- Authentication: Bắt buộc Bearer JWT
- Role/permission: Chỉ owner của video.
- Content-Type: Không có body
- Trạng thái xác minh: **Đã test** — ownership và soft-delete trong collection.

**A. Path parameters**: `video_id` — UUID, bắt buộc.

**B. Query parameters**: Không có.

**C. Headers**

```http
Authorization: Bearer <access_token>
```

**D. Request body**: Không có.

**E. Response**: HTTP `204 No Content`, không có JSON body.

**F. Lỗi thường gặp**

- `401`: thiếu/sai JWT.
- `404`: video không tồn tại hoặc caller không phải owner.
- `422`: video ID không hợp lệ.

**G. Ví dụ gọi API**

```bash
curl -X DELETE http://127.0.0.1:8000/api/v1/videos/<video_id> ^
  -H "Authorization: Bearer <access_token>"
```

### 3.10 Tạo content report

**Thông tin chung**

- Method: `POST`
- Path: `/api/v1/videos/{video_id}/reports`
- Operation ID: `create_report`
- Full URL mẫu: `http://127.0.0.1:8000/api/v1/videos/<video_id>/reports`
- Chức năng: báo cáo video vi phạm.
- Module: Content Report
- Authentication: Bắt buộc Bearer JWT
- Role/permission: User active; không yêu cầu moderator/admin.
- Content-Type: `application/json`
- Trạng thái xác minh: **Đã test** — Content Report collection.

**A. Path parameters**: `video_id` — UUID, bắt buộc.

**B. Query parameters**: Không có.

**C. Headers**

```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

**D. Request body**

```json
{"reason": "Content violates local moderation policy"}
```

| Trường | Kiểu | Bắt buộc | Quy tắc |
|---|---|---:|---|
| `reason` | string | Có | 3–1000 ký tự |

**E. Response mẫu**

```json
{
  "id": "00000000-0000-0000-0000-000000000003",
  "video_id": "00000000-0000-0000-0000-000000000002",
  "reason": "Content violates local moderation policy",
  "status": "open"
}
```

HTTP `201`. Nếu video đang `published`, endpoint chuyển video sang
`pending_review`.

**F. Lỗi thường gặp**

- `401`: thiếu/sai JWT.
- `404`: video không tồn tại hoặc đã soft-delete.
- `409`: user đã có report `open` cho video này.
- `422`: thiếu reason hoặc reason ngoài giới hạn.

**G. Ví dụ gọi API**

```bash
curl -X POST http://127.0.0.1:8000/api/v1/videos/<video_id>/reports ^
  -H "Authorization: Bearer <access_token>" ^
  -H "Content-Type: application/json" ^
  -d "{\"reason\":\"Content violates local moderation policy\"}"
```

### 3.11 Moderation queue

**Thông tin chung**

- Method: `GET`
- Path: `/api/v1/moderation/queue`
- Operation ID: `moderation_queue`
- Full URL mẫu: `http://127.0.0.1:8000/api/v1/moderation/queue`
<<<<<<< HEAD
- Chức năng: liệt kê video `pending_review`, chưa bị xóa.
=======
- Chức năng: Liệt kê các video đang ở trạng thái `pending_review` (chờ duyệt) kèm dữ liệu tổng hợp giàu ngữ cảnh từ AI và báo cáo người dùng (UC012).
>>>>>>> 0dcf2c46a0f557080b0fcca8ac5384151d871ffd
- Module: Moderation
- Authentication: Bắt buộc Bearer JWT
- Role/permission: `moderator` hoặc `admin`.
- Content-Type: Không có body
<<<<<<< HEAD
- Trạng thái xác minh: **Đã test** — Moderation collection.
=======
- Trạng thái xác minh: **Đã test** — Test suite `test_labels_appeals_admin.py` & Pytest integration.
>>>>>>> 0dcf2c46a0f557080b0fcca8ac5384151d871ffd

**A/B. Path và query parameters**: Không có.

**C. Headers**

```http
Authorization: Bearer <moderator_or_admin_token>
```

**D. Request body**: Không có.

<<<<<<< HEAD
**E. Response**: HTTP `200`, mảng `VideoResponse`; có thể là `[]`.

**F. Lỗi thường gặp**

- `401`: thiếu/sai JWT.
- `403`: user không có role moderator/admin.
=======
**E. Response mẫu**

Response Model: `list[ModerationQueueItemResponse]`

```json
[
  {
    "id": "96224541-e76c-4d10-bc56-607b07e103c1",
    "original_filename": "dance_video.mp4",
    "caption": "Màn nhảy sôi động",
    "visibility": "public",
    "allow_comments": true,
    "size_bytes": 1348261,
    "status": "pending_review",
    "created_at": "2026-11-03T00:57:30Z",
    "owner_name": "NguyenVanA",
    "thumbnail_url": "https://pub-example.r2.dev/thumbnails/96224541-e76c-4d10-bc56-607b07e103c1.jpg",
    "stream_url": "/api/v1/videos/96224541-e76c-4d10-bc56-607b07e103c1/stream",
    "ai_status": "succeeded",
    "labels": [
      {
        "name": "Suggestive",
        "confidence": 0.55,
        "level": "MEDIUM",
        "source": "ai"
      }
    ],
    "queue_reason": "AI nghi vấn vi phạm (Suggestive 55%)",
    "report_count": 0
  }
]
```

**Bảng chi tiết các trường trong `ModerationQueueItemResponse`:**

| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | UUID | ID của video trong hàng đợi |
| `original_filename` | string | Tên file gốc khi người dùng tải lên |
| `caption` | string/null | Tiêu đề hoặc chú thích video |
| `visibility` | string | Quyền xem: `"public"` hoặc `"private"` |
| `allow_comments` | boolean | Cờ cho phép người xem bình luận |
| `size_bytes` | integer | Kích thước video tính bằng byte |
| `status` | string | Trạng thái hiện tại: luôn là `"pending_review"` |
| `created_at` | ISO datetime | Thời điểm video được tải lên |
| `owner_name` | string/null | Tên hiển thị của tác giả đăng tải |
| `thumbnail_url` | string/null | URL ảnh thu nhỏ trích xuất từ khung hình đầu tiên của video |
| `stream_url` | string/null | URL phát luồng trực tiếp phục vụ trình duyệt video của Moderator |
| `ai_status` | string/null | Trạng thái tiến trình AI: `"succeeded"`, `"running"`, `"failed"`, `"pending"` |
| `labels` | list[LabelResponse] | Danh sách nhãn do AI hoặc thủ công gán (kèm confidence, level, source) |
| `queue_reason` | string | Lý do cụ thể video bị đưa vào hàng đợi (tổng hợp từ nhãn AI nghi vấn hoặc số lượt report) |
| `report_count` | integer | Số lượng báo cáo mở (`open`) từ người dùng về video này |

**F. Lỗi thường gặp**

- `401 Unauthorized`: Thiếu hoặc sai Bearer JWT token.
- `403 Forbidden`: Người dùng không có role `moderator` hoặc `admin`.
>>>>>>> 0dcf2c46a0f557080b0fcca8ac5384151d871ffd

**G. Ví dụ gọi API**

```bash
curl http://127.0.0.1:8000/api/v1/moderation/queue ^
  -H "Authorization: Bearer <moderator_or_admin_token>"
```

### 3.12 Quyết định trạng thái video

**Thông tin chung**

- Method: `POST`
- Path: `/api/v1/moderation/videos/{video_id}/decision`
- Operation ID: `moderation_decision`
- Full URL mẫu: `http://127.0.0.1:8000/api/v1/moderation/videos/<video_id>/decision`
<<<<<<< HEAD
- Chức năng: moderator/admin approve hoặc reject video.
=======
- Chức năng: Moderator/Admin phê duyệt (`approve`) hoặc từ chối (`reject`) video trong hàng đợi kiểm duyệt (UC014).
>>>>>>> 0dcf2c46a0f557080b0fcca8ac5384151d871ffd
- Module: Moderation
- Authentication: Bắt buộc Bearer JWT
- Role/permission: `moderator` hoặc `admin`.
- Content-Type: `application/json`
<<<<<<< HEAD
- Trạng thái xác minh: **Code/OpenAPI** — route/schema đã đối chiếu; chưa có
  request Newman riêng cho endpoint này.

**A. Path parameters**: `video_id` — UUID, bắt buộc.
=======
- Trạng thái xác minh: **Đã test** — Test suite `test_labels_appeals_admin.py`.

**A. Path parameters**: `video_id` — UUID của video cần phán quyết, bắt buộc.
>>>>>>> 0dcf2c46a0f557080b0fcca8ac5384151d871ffd

**B. Query parameters**: Không có.

**C. Headers**

```http
Authorization: Bearer <moderator_or_admin_token>
Content-Type: application/json
```

**D. Request body**

<<<<<<< HEAD
```json
{
  "action": "approve",
  "reason": "Review completed"
}
```

| Trường | Kiểu | Bắt buộc | Giá trị |
|---|---|---:|---|
| `action` | enum | Có | `approve` hoặc `reject` |
| `reason` | string/null | Không | Tối đa 1000 ký tự; mặc định `null` |

`approve` chuyển video sang `published`; action khác hợp lệ là `reject`, chuyển
sang `rejected`. Endpoint lưu `ModerationReview`.

**E. Response**: HTTP `204 No Content`.

**F. Lỗi thường gặp**

- `401`: thiếu/sai JWT.
- `403`: không phải moderator/admin.
- `404`: video không tồn tại hoặc đã xóa.
- `422`: UUID hoặc action/reason sai schema.
=======
Request Model: `ModerationDecisionRequest`

```json
{
  "action": "reject",
  "reason": "Phát hiện nội dung nhạy cảm vi phạm tiêu chuẩn cộng đồng (Adult/Suggestive)."
}
```

| Trường | Kiểu | Bắt buộc | Quy tắc & Ý nghĩa |
|---|---|---:|---|
| `action` | enum | Có | Chỉ chấp nhận `"approve"` (duyệt đăng) hoặc `"reject"` (từ chối/gỡ bỏ) |
| `reason` | string/null | Phụ thuộc | **QUY TẮC RÀNG BUỘC (SRS Luồng 4a.1):**<br>- Khi `action == "reject"`: `reason` **BẮT BUỘC** phải có và không được là chuỗi rỗng hoặc chỉ có khoảng trắng (tối đa 1000 ký tự). Nếu thiếu hoặc rỗng, API sẽ từ chối với HTTP `422 Unprocessable Entity` kèm thông báo *"Lý do từ chối là bắt buộc."*.<br>- Khi `action == "approve"`: `reason` là tùy chọn (`null` hoặc string). |

**Hành vi xử lý:**
- Khi `action == "approve"`: `video.status` chuyển thành `published`, video xuất hiện ngay trên Feed công khai.
- Khi `action == "reject"`: `video.status` chuyển thành `rejected`, video bị ẩn vĩnh viễn khỏi Feed.
- Cả hai hành động đều tạo bản ghi `ModerationReview` lưu lại ID kiểm duyệt viên, hành động (`approve`/`reject`), lý do giải trình (`reason`), và thời gian xử lý.

**E. Response**: HTTP `204 No Content` (không có response body khi thành công).

**F. Lỗi thường gặp**

- `401 Unauthorized`: Thiếu hoặc sai Bearer JWT token.
- `403 Forbidden`: Người gọi không có role `moderator` hoặc `admin`.
- `404 Not Found`: Video không tồn tại hoặc đã bị xóa mềm (`is_deleted = true`).
- `422 Unprocessable Entity`: UUID sai định dạng, `action` không hợp lệ, hoặc chọn `"reject"` nhưng bỏ trống trường `reason`.
>>>>>>> 0dcf2c46a0f557080b0fcca8ac5384151d871ffd

**G. Ví dụ gọi API**

```bash
<<<<<<< HEAD
curl -X POST http://127.0.0.1:8000/api/v1/moderation/videos/<video_id>/decision ^
  -H "Authorization: Bearer <moderator_or_admin_token>" ^
  -H "Content-Type: application/json" ^
  -d "{\"action\":\"approve\",\"reason\":\"Review completed\"}"
=======
# Từ chối video (bắt buộc kèm reason)
curl -X POST "http://127.0.0.1:8000/api/v1/moderation/videos/<video_id>/decision" ^
  -H "Authorization: Bearer <moderator_token>" ^
  -H "Content-Type: application/json" ^
  -d "{"action":"reject","reason":"Vi pham tieu chuan cong dong."}"

# Phê duyệt video
curl -X POST "http://127.0.0.1:8000/api/v1/moderation/videos/<video_id>/decision" ^
  -H "Authorization: Bearer <moderator_token>" ^
  -H "Content-Type: application/json" ^
  -d "{"action":"approve"}"
>>>>>>> 0dcf2c46a0f557080b0fcca8ac5384151d871ffd
```

### 3.13 Danh sách report mở

**Thông tin chung**

- Method: `GET`
- Path: `/api/v1/moderation/reports`
- Operation ID: `moderation_reports`
- Full URL mẫu: `http://127.0.0.1:8000/api/v1/moderation/reports`
- Chức năng: liệt kê report có status `open`.
- Module: Moderation
- Authentication: Bắt buộc Bearer JWT
- Role/permission: `moderator` hoặc `admin`.
- Content-Type: Không có body
- Trạng thái xác minh: **Đã test** — Moderation collection.

**A/B. Path và query parameters**: Không có.

**C. Headers**

```http
Authorization: Bearer <moderator_or_admin_token>
```

**D. Request body**: Không có.

**E. Response**: HTTP `200`, mảng `ReportResponse` (`id`, `video_id`,
`video_caption`, `reason`, `status`); có thể là `[]`. `video_caption` là mô tả
hoặc tên tệp của video bị báo cáo để moderator nhận ra video.

**F. Lỗi thường gặp**

- `401`: thiếu/sai JWT.
- `403`: không phải moderator/admin.

**G. Ví dụ gọi API**

```bash
curl http://127.0.0.1:8000/api/v1/moderation/reports ^
  -H "Authorization: Bearer <moderator_or_admin_token>"
```

### 3.14 Quyết định report

**Thông tin chung**

- Method: `POST`
- Path: `/api/v1/moderation/reports/{report_id}/decision`
- Operation ID: `report_decision`
- Full URL mẫu: `http://127.0.0.1:8000/api/v1/moderation/reports/<report_id>/decision`
- Chức năng: xử lý một report đang mở và cập nhật video liên quan.
- Module: Moderation
- Authentication: Bắt buộc Bearer JWT
- Role/permission: `moderator` hoặc `admin`.
- Content-Type: `application/json`
- Trạng thái xác minh: **Đã test** — Moderation collection với approve và
  kiểm tra xử lý lặp.

**A. Path parameters**: `report_id` — UUID, bắt buộc.

**B. Query parameters**: Không có.

**C. Headers**

```http
Authorization: Bearer <moderator_or_admin_token>
Content-Type: application/json
```

**D. Request body**

```json
{
  "action": "approve",
  "reason": "Policy violation confirmed"
}
```

`action` nhận `approve` hoặc `reject`; `reason` nullable, tối đa 1000 ký tự.
Theo implementation hiện tại, `approve` làm video `rejected` và report
`rejected`; `reject` làm video `published` và report `resolved`. Cách đặt tên
action này là behavior thực tế của code, cần được Frontend tích hợp đúng.

**E. Response**: HTTP `204 No Content`.

**F. Lỗi thường gặp**

- `401`: thiếu/sai JWT.
- `403`: không phải moderator/admin.
- `404`: report không tồn tại, report không còn `open`, hoặc video liên quan
  không tồn tại.
- `422`: UUID hoặc body sai schema.

**G. Ví dụ gọi API**

```bash
curl -X POST http://127.0.0.1:8000/api/v1/moderation/reports/<report_id>/decision ^
  -H "Authorization: Bearer <moderator_or_admin_token>" ^
  -H "Content-Type: application/json" ^
  -d "{\"action\":\"approve\",\"reason\":\"Policy violation confirmed\"}"
```

### 3.15 Admin list/search users

**Thông tin chung**

- Method: `GET`
- Path: `/api/v1/admin/users`
- Operation ID: `admin_list_users`
<<<<<<< HEAD
- Full URL mẫu: `http://127.0.0.1:8000/api/v1/admin/users?search=Managed`
- Chức năng: Admin xem danh sách user và tìm theo email/display name.
- Module: Admin Management
- Authentication: Bearer JWT
- Role/permission: `admin`
- Trạng thái xác minh: **Đã test** — Admin Management Newman.

**Parameters and headers**

- Query `search`: string, không bắt buộc; tìm theo `email` hoặc `display_name`.
- Không có path parameter hoặc request body.
=======
- Full URL mẫu: `http://127.0.0.1:8000/api/v1/admin/users?role=user&status=active&search=Managed&skip=0&limit=50`
- Chức năng: Admin xem danh sách user, tìm kiếm theo email/display name, lọc theo vai trò (`role`) và trạng thái hoạt động (`status`/`is_active`), hỗ trợ phân trang (`skip`, `limit`).
- Module: Admin Management
- Authentication: Bearer JWT
- Role/permission: `admin`
- Trạng thái xác minh: **Đã test** — Pytest `test_admin_user_management_filters_and_banning` & Admin Management Newman.

**Parameters and headers**

- Query parameters:
  - `search`: string, không bắt buộc; tìm kiếm chuỗi trong `email` hoặc `display_name`.
  - `role`: string enum (`user`, `moderator`, `admin`), không bắt buộc; lọc theo vai trò.
  - `status`: string (`active`, `banned`), không bắt buộc; lọc theo trạng thái tài khoản.
  - `is_active`: boolean (`true`, `false`), không bắt buộc; lọc theo cờ hoạt động.
  - `skip`: integer (mặc định `0`, >= 0); offset phân trang.
  - `limit`: integer (mặc định `50`, từ 1 đến 100); số bản ghi mỗi trang.
>>>>>>> 0dcf2c46a0f557080b0fcca8ac5384151d871ffd
- Header: `Authorization: Bearer <admin_token>`.

**Response và lỗi**

<<<<<<< HEAD
- HTTP `200`, mảng user summary gồm `id`, `display_name`, `role`, `is_active`,
  `created_at`.
- `401` token thiếu/sai hoặc user inactive; `403` không phải admin.

```bash
curl "http://127.0.0.1:8000/api/v1/admin/users?search=Managed" ^
=======
- HTTP `200`, mảng user summary:
  ```json
  [
    {
      "id": "76628c89-63ff-4e78-958d-71b55c689ba4",
      "display_name": "Người dùng mẫu",
      "email": "user@example.com",
      "role": "user",
      "is_active": true,
      "created_at": "2026-11-03T02:00:00Z"
    }
  ]
  ```
- `401 Unauthorized`: Token thiếu/sai hoặc user bị khóa; `403 Forbidden`: Người dùng không có vai trò `admin`.

```bash
curl "http://127.0.0.1:8000/api/v1/admin/users?role=user&status=banned" ^
>>>>>>> 0dcf2c46a0f557080b0fcca8ac5384151d871ffd
  -H "Authorization: Bearer <admin_token>"
```

### 3.16 Admin xem chi tiết user

- Method: `GET`
- Path: `/api/v1/admin/users/{user_id}`
- Operation ID: `admin_get_user`
- Authentication: Bearer JWT, role `admin`
- Response: HTTP `200`, gồm summary và `email`.
- Path `user_id`: UUID, bắt buộc.
- Request body/query: Không có.
- Lỗi: `401`, `403`, `404` nếu user không tồn tại, hoặc `422` nếu UUID sai.
- Trạng thái xác minh: **Đã test** — Admin Management Newman.

```bash
curl http://127.0.0.1:8000/api/v1/admin/users/<user_id> ^
  -H "Authorization: Bearer <admin_token>"
```

### 3.17 Admin khóa hoặc mở user

- Method: `PATCH`
- Path: `/api/v1/admin/users/{user_id}/status`
- Operation ID: `admin_update_user_status`
- Authentication: Bearer JWT, role `admin`
- Path `user_id`: UUID, bắt buộc.
- Content-Type: `application/json`
<<<<<<< HEAD
- Body: `{"is_active": false}` hoặc `{"is_active": true}`; `is_active` bắt buộc
  là boolean.
- Response: HTTP `200`, user detail sau cập nhật.
- Lỗi: `400` nếu admin tự khóa chính mình; `401`, `403`, `404`, `422` theo auth,
  quyền, ID và schema.
- Trạng thái xác minh: **Đã test** — Admin Management Newman.
=======
- Body: Hỗ trợ linh hoạt cả 2 định dạng:
  - Boolean: `{"is_active": false}` (khóa) hoặc `{"is_active": true}` (mở khóa).
  - String status: `{"status": "banned"}` (khóa) hoặc `{"status": "active"}` (mở khóa).
- Response: HTTP `200`, user detail sau cập nhật.
- Cơ chế bảo vệ & bảo mật:
  - Khi tài khoản bị khóa (`is_active = false`), mọi request kèm token của user đó sẽ bị chặn ngay lập tức (HTTP `401 Unauthorized` "Tài khoản không hợp lệ").
  - Admin không thể tự khóa chính mình (`403 Forbidden`).
- Lỗi: `400` / `403` nếu admin tự khóa tài khoản của mình; `401`, `403`, `404`, `422` theo auth, quyền, ID và schema.
- Trạng thái xác minh: **Đã test** — Pytest `test_admin_user_management_filters_and_banning`.
>>>>>>> 0dcf2c46a0f557080b0fcca8ac5384151d871ffd

```bash
curl -X PATCH http://127.0.0.1:8000/api/v1/admin/users/<user_id>/status ^
  -H "Authorization: Bearer <admin_token>" ^
  -H "Content-Type: application/json" ^
<<<<<<< HEAD
  -d "{\"is_active\":false}"
=======
  -d "{"status":"banned"}"
>>>>>>> 0dcf2c46a0f557080b0fcca8ac5384151d871ffd
```

### 3.18 Admin xem danh sách moderator

- Method: `GET`
- Path: `/api/v1/admin/moderators`
- Operation ID: `admin_list_moderators`
- Authentication: Bearer JWT, role `admin`
- Path/query/body: Không có.
- Response: HTTP `200`, mảng user summary có role `moderator` hoặc `admin`.
- Lỗi: `401` hoặc `403`.
- Trạng thái xác minh: **Đã test** — Admin Management Newman.

```bash
curl http://127.0.0.1:8000/api/v1/admin/moderators ^
  -H "Authorization: Bearer <admin_token>"
```

### 3.19 Admin cấp hoặc thu hồi role

- Method: `PATCH`
- Path: `/api/v1/admin/users/{user_id}/role`
- Operation ID: `admin_update_user_role`
- Authentication: Bearer JWT, role `admin`
- Path `user_id`: UUID, bắt buộc.
- Content-Type: `application/json`
- Body: `{"role":"user"}`, `{"role":"moderator"}` hoặc `{"role":"admin"}`.
- Response: HTTP `200`, user detail sau cập nhật.
- Lỗi: `400` nếu admin tự thu hồi quyền admin; `401`, `403`, `404`, `422` theo
  auth, quyền, ID và enum.
- Trạng thái xác minh: **Đã test** — Admin Management Newman đã cấp role
  `moderator`.
- SRS còn thiếu: `Senior Moderator`, audit log, notification, session revoke
  và unassign công việc locked chưa được code.

```bash
curl -X PATCH http://127.0.0.1:8000/api/v1/admin/users/<user_id>/role ^
  -H "Authorization: Bearer <admin_token>" ^
  -H "Content-Type: application/json" ^
  -d "{\"role\":\"moderator\"}"
```

<<<<<<< HEAD
=======
### 3.19.1 Admin tra cứu nhật ký kiểm duyệt & kiểm toán hệ thống (Audit Logs)

**Thông tin chung**

- Method: `GET`
- Path: `/api/v1/admin/audit-logs`
- Operation ID: `admin_list_audit_logs`
- Full URL mẫu: `http://127.0.0.1:8000/api/v1/admin/audit-logs?action=reject&limit=20`
- Chức năng: Admin tra cứu toàn bộ lịch sử các quyết định kiểm duyệt video trong hệ thống (ai thực hiện: moderator display name/email hoặc "Hệ thống AI", video nào: ID, tiêu đề, người đăng, quyết định: approve/reject, lý do xử lý vi phạm, thời gian quyết định).
- Module: Admin Management & Audit
- Authentication: Bearer JWT
- Role/permission: `admin` (Kiểm duyệt viên thường hoặc người dùng bị từ chối với HTTP `403 Forbidden`).
- Trạng thái xác minh: **Đã test** — Pytest `test_admin_audit_logs_and_permissions`.

**Parameters and headers**

- Query parameters:
  - `action`: string (`approve`, `reject`), không bắt buộc; lọc theo hành vi phê duyệt hoặc từ chối.
  - `moderator_id`: UUID, không bắt buộc; lọc theo ID của kiểm duyệt viên cụ thể.
  - `video_id`: UUID, không bắt buộc; lọc theo video cụ thể.
  - `skip`: integer (mặc định `0`, >= 0); offset phân trang.
  - `limit`: integer (mặc định `50`, tối đa 100); số bản ghi mỗi trang.
- Header: `Authorization: Bearer <admin_token>`.

**Response JSON mẫu**

- HTTP `200`:
  ```json
  [
    {
      "id": "c1f7b7e2-8924-42f4-a8c7-4c74a019488a",
      "video_id": "90db1680-bc96-410a-b333-6cf7fa50ebc5",
      "video_caption": "Video ngắn hướng dẫn",
      "video_owner_id": "f51675c9-959c-4ee3-979d-da3e30f576e9",
      "video_owner_name": "Tác giả video",
      "moderator_id": "8bb38ce2-4753-488f-a9cb-b09a473ee16a",
      "moderator_name": "Kiểm duyệt viên 01",
      "moderator_email": "mod01@example.com",
      "action": "reject",
      "reason": "Vi phạm tiêu chuẩn cộng đồng về nội dung nhạy cảm",
      "created_at": "2026-11-03T03:10:00Z"
    }
  ]
  ```

**Bảng mã lỗi**

- `401 Unauthorized`: Chưa truyền token hoặc token hết hạn/không hợp lệ.
- `403 Forbidden`: Người dùng không có vai trò `admin` (kể cả role `moderator` hay `user`).

```bash
curl "http://127.0.0.1:8000/api/v1/admin/audit-logs?action=reject" ^
  -H "Authorization: Bearer <admin_token>"
```

>>>>>>> 0dcf2c46a0f557080b0fcca8ac5384151d871ffd
### 3.20 Phát video (stream)

**Thông tin chung**

- Method: `GET`
- Path: `/api/v1/videos/{video_id}/stream`
- Operation ID: `stream_video`
- Full URL mẫu: `http://127.0.0.1:8000/api/v1/videos/<video_id>/stream`
- Chức năng: trả tệp MP4 để trình duyệt phát trực tiếp (feed, hồ sơ, hàng đợi kiểm duyệt).
- Module: Video Management
- Authentication: Không bắt buộc; `Authorization` chỉ cần khi video chưa `published`.
- Role/permission: video `published` cho mọi người; video chưa publish chỉ cho chủ video, `moderator`, `admin`.
- Content-Type: `video/mp4`
- Trạng thái xác minh: **Đã test** — Pytest `test_video_stream_serves_published_video_and_hides_pending_one`.

**A/B. Path và query parameters**: path `video_id` (UUID). Không có query.

**C. Headers**: tùy chọn `Authorization: Bearer <access_token>`.

**D. Request body**: Không có.

**E. Response**:

- Với S3/R2 và video public: HTTP `307 Temporary Redirect` tới
  `S3_PUBLIC_DOMAIN/videos/<video_id>.mp4`; CDN trả `200` hoặc `206 Partial
  Content` cho Range Request.
- Với local legacy storage: HTTP `200` với body là tệp MP4 và header
  `Cache-Control: private, max-age=60`; Range có thể trả `206`.

**F. Lỗi thường gặp**

- `404`: video không tồn tại, đã soft-delete, chưa `published` mà caller không có quyền, hoặc tệp không còn trong `UPLOAD_DIR`.
- `307`: redirect bình thường sang CDN R2, không phải lỗi.

**G. Ví dụ gọi API**

```bash
curl -OJ http://127.0.0.1:8000/api/v1/videos/<video_id>/stream
```

<<<<<<< HEAD
=======
### 3.21 Gửi khiếu nại video (Appeals - UC011)

**Thông tin chung**

- Method: `POST`
- Path: `/api/v1/videos/{video_id}/appeals`
- Operation ID: `create_appeal`
- Full URL mẫu: `http://127.0.0.1:8000/api/v1/videos/<video_id>/appeals`
- Chức năng: Chủ sở hữu video gửi khiếu nại yêu cầu xem xét lại đối với video bị từ chối (`rejected`). Chống trùng lặp khiếu nại đang mở.
- Module: Video Management / Moderation
- Authentication: Bearer JWT
- Role/permission: Chủ sở hữu (`owner`) của video.
- Trạng thái xác minh: **Đã test** — Pytest `test_appeal_lifecycle`.

**A/B. Path và query parameters**: path `video_id` (UUID). Không có query.

**C. Headers**: `Authorization: Bearer <owner_token>`, `Content-Type: application/json`.

**D. Request body**:

```json
{
  "reason": "Nội dung video không vi phạm tiêu chuẩn cộng đồng, xin xem xét lại."
}
```

**E. Response**: HTTP `201 Created`

```json
{
  "id": "11111111-2222-3333-4444-555555555555",
  "video_id": "99999999-8888-7777-6666-555555555555",
  "user_id": "00000000-1111-2222-3333-444444444444",
  "reason": "Nội dung video không vi phạm tiêu chuẩn cộng đồng, xin xem xét lại.",
  "status": "open",
  "moderator_id": null,
  "decision_reason": null,
  "created_at": "2026-11-02T12:00:00Z",
  "decided_at": null,
  "user_display_name": null
}
```

**F. Lỗi thường gặp**:
- `400`: Video chưa bị từ chối (không ở trạng thái `rejected`).
- `404`: Video không tồn tại hoặc người gọi không phải chủ sở hữu.
- `409`: Video đã có khiếu nại đang chờ xử lý (`open`).

### 3.22 Hàng đợi duyệt khiếu nại (Moderator/Admin - UC017)

**Thông tin chung**

- Method: `GET`
- Path: `/api/v1/moderation/appeals`
- Operation ID: `moderation_appeals`
- Full URL mẫu: `http://127.0.0.1:8000/api/v1/moderation/appeals`
- Chức năng: Kiểm duyệt viên hoặc Quản trị viên xem danh sách các khiếu nại đang mở.
- Module: Moderation
- Authentication: Bearer JWT
- Role/permission: `moderator` hoặc `admin`.
- Trạng thái xác minh: **Đã test** — Pytest `test_appeal_lifecycle`.

**Response**: HTTP `200 OK`, mảng các đối tượng khiếu nại kèm `user_display_name`.

### 3.23 Phán quyết khiếu nại (Moderator/Admin - UC017)

**Thông tin chung**

- Method: `POST`
- Path: `/api/v1/moderation/appeals/{appeal_id}/decision`
- Operation ID: `appeal_decision`
- Full URL mẫu: `http://127.0.0.1:8000/api/v1/moderation/appeals/<appeal_id>/decision`
- Chức năng: Phê duyệt (`approve` -> chuyển video sang `published`) hoặc bác bỏ (`reject` -> video giữ nguyên `rejected`) khiếu nại kèm lý do và ghi nhận audit log.
- Module: Moderation
- Authentication: Bearer JWT
- Role/permission: `moderator` hoặc `admin`.
- Trạng thái xác minh: **Đã test** — Pytest `test_appeal_lifecycle`, `test_appeal_rejected_keeps_video_hidden`.

**Request body**:

```json
{
  "action": "approve",
  "reason": "Video hợp lệ sau khi kiểm tra lại"
}
```

**Response**: HTTP `204 No Content`.

### 3.24 Moderator thay thế nhãn video (UC015)

**Thông tin chung**

- Method: `PATCH`
- Path: `/api/v1/videos/{video_id}/labels`
- Operation ID: `replace_labels`
- Full URL mẫu: `http://127.0.0.1:8000/api/v1/videos/<video_id>/labels`
- Chức năng: Kiểm duyệt viên / Admin can thiệp ghi đè toàn bộ danh sách nhãn của video.
- Module: Moderation / Label Management
- Authentication: Bearer JWT
- Role/permission: `moderator` hoặc `admin` (Owner trả về 403).
- Trạng thái xác minh: **Đã test** — Pytest `test_moderator_replaces_labels_and_owner_cannot`.

**Request body**:

```json
{
  "labels": [
    {"name": "Adult", "confidence": 0.9}
  ]
}
```

**Response**: HTTP `200 OK`, danh sách nhãn mới đã cập nhật.

### 3.25 Quản trị nhãn nội dung: Tạo nhãn (Admin)

**Thông tin chung**

- Method: `POST`
- Path: `/api/v1/admin/labels`
- Operation ID: `admin_create_label`
- Full URL mẫu: `http://127.0.0.1:8000/api/v1/admin/labels`
- Chức năng: Quản trị viên tạo mới nhãn chuẩn trong hệ thống. Chống trùng tên không phân biệt hoa thường.
- Module: Admin Management
- Authentication: Bearer JWT
- Role/permission: `admin`
- Trạng thái xác minh: **Đã test** — Pytest `test_admin_label_crud`.

**Request body**: `{"name": "Violence"}`  
**Response**: HTTP `201 Created` kèm `video_count: 0`.

### 3.26 Quản trị nhãn nội dung: Danh sách nhãn (Admin)

**Thông tin chung**

- Method: `GET`
- Path: `/api/v1/admin/labels`
- Operation ID: `admin_list_labels`
- Chức năng: Quản trị viên xem toàn bộ nhãn hệ thống kèm số video đang được gán nhãn đó.
- Module: Admin Management
- Authentication: Bearer JWT
- Role/permission: `admin`
- Trạng thái xác minh: **Đã test** — Pytest `test_admin_label_crud`.

### 3.27 Quản trị nhãn nội dung: Sửa/Vô hiệu hóa nhãn (Admin)

**Thông tin chung**

- Method: `PATCH`
- Path: `/api/v1/admin/labels/{label_id}`
- Operation ID: `admin_update_label`
- Chức năng: Quản trị viên đổi tên hoặc bật/tắt kích hoạt nhãn (`is_active`). Yêu cầu cung cấp ít nhất 1 trường (tránh body rỗng 422).
- Module: Admin Management
- Authentication: Bearer JWT
- Role/permission: `admin`
- Trạng thái xác minh: **Đã test** — Pytest `test_admin_label_crud`.

### 3.28 Quản trị cập nhật trạng thái video (Admin)

**Thông tin chung**

- Method: `PATCH`
- Path: `/api/v1/admin/videos/{video_id}/status`
- Operation ID: `admin_update_video_status`
- Chức năng: Admin can thiệp trạng thái video (`published`, `rejected`, `deleted` - soft delete) kèm lưu vết audit record trong `ModerationReview`.
- Module: Admin Management
- Authentication: Bearer JWT
- Role/permission: `admin`
- Trạng thái xác minh: **Đã test** — Pytest `test_admin_updates_video_status_with_soft_delete`.

**Request body**: `{"status": "rejected", "reason": "Vi phạm quy chế"}` hoặc `{"status": "deleted"}`.  
**Response**: HTTP `200 OK` với thông tin VideoResponse.

### 3.29 Thống kê hệ thống & tổng quan Dashboard (Admin - UC020)

**Thông tin chung**

- Method: `GET`
- Paths hỗ trợ đồng thời: `/api/v1/admin/stats` và `/api/v1/admin/overview`
- Operation ID: `admin_get_stats`
- Full URL mẫu: `http://127.0.0.1:8000/api/v1/admin/overview?days=30`
- Chức năng: Cung cấp số liệu thống kê toàn diện cho Admin Dashboard:
  - Khối chỉ số tổng quan nhanh (`summary`): Tổng số người dùng, tổng số video, số video đã duyệt (`published`), số video bị từ chối (`rejected`), số video chờ duyệt (`pending_review`), số báo cáo chờ xử lý (`open`), số khiếu nại đang mở (`open`), tỷ lệ chính xác/thành công AI (`ai_accuracy_rate`).
  - Khối chi tiết: Phân bố video theo trạng thái, báo cáo theo trạng thái, khiếu nại theo trạng thái, tác vụ AI và khối lượng công việc của từng kiểm duyệt viên.
- Module: Admin Management
- Authentication: Bearer JWT
- Role/permission: `admin` (người dùng khác nhận `403 Forbidden`).
- Trạng thái xác minh: **Đã test** — Pytest `test_admin_stats_and_overview_summary` & `test_moderator_and_system_stats`.

**Parameters and headers**

- Query parameter: `days` (mặc định 30, tối thiểu 1); khoảng thời gian thống kê (ngày gần nhất).
- Header: `Authorization: Bearer <admin_token>`.

**Response JSON mẫu**

- HTTP `200`:
  ```json
  {
    "days": 30,
    "summary": {
      "total_users": 150,
      "total_videos": 420,
      "published_videos": 380,
      "rejected_videos": 25,
      "pending_videos": 15,
      "pending_reports": 4,
      "open_appeals": 2,
      "ai_accuracy_rate": 98.5
    },
    "videos_by_status": {
      "processing": 0,
      "pending_review": 15,
      "published": 380,
      "rejected": 25,
      "failed": 0,
      "deleted": 5
    },
    "reports_by_status": {
      "open": 4,
      "resolved": 12,
      "rejected": 3
    },
    "appeals_by_status": {
      "open": 2,
      "approved": 5,
      "rejected": 8
    },
    "jobs_by_status": {
      "pending": 0,
      "running": 1,
      "succeeded": 415,
      "failed": 4
    },
    "moderator_workload": [
      {
        "moderator_id": "8bb38ce2-4753-488f-a9cb-b09a473ee16a",
        "moderator_name": "Kiểm duyệt viên 01",
        "reviews_count": 45,
        "appeals_count": 8
      }
    ]
  }
  ```

**Bảng mã lỗi**

- `401 Unauthorized`: Chưa đăng nhập hoặc token không hợp lệ.
- `403 Forbidden`: Không có vai trò `admin`.
- `422 Unprocessable Entity`: Giá trị `days` nhỏ hơn 1 hoặc không phải số nguyên.

```bash
curl "http://127.0.0.1:8000/api/v1/admin/overview?days=30" ^
  -H "Authorization: Bearer <admin_token>"
```

### 3.30 Thống kê hiệu suất Moderator (Admin - UC019)

**Thông tin chung**

- Method: `GET`
- Path: `/api/v1/admin/moderators/{moderator_id}/stats`
- Operation ID: `admin_get_moderator_stats`
- Path parameters: `moderator_id` (UUID).
- Chức năng: Xem số video đã duyệt (`videos_reviewed`) và số khiếu nại đã xử lý (`appeals_handled`) của kiểm duyệt viên.
- Module: Admin Management
- Authentication: Bearer JWT
- Role/permission: `admin`
- Trạng thái xác minh: **Đã test** — Pytest `test_moderator_and_system_stats`.

### 3.31 Làm mới token (Refresh Token)

**Thông tin chung**

- Method: `POST`
- Path: `/api/v1/auth/refresh`
- Operation ID: `refresh`
- Full URL mẫu: `http://127.0.0.1:8000/api/v1/auth/refresh`
- Chức năng: Xoay vòng (rotation) refresh token, cấp cặp access token và refresh token mới, thu hồi token cũ.
- Module: Auth
- Authentication: Không yêu cầu (dùng opaque refresh token trong body)
- Role/permission: Không có
- Content-Type: `application/json`
- Trạng thái xác minh: **Đã test** — Pytest `test_auth_session.py`.

**A/B. Path và query parameters**: Không có.

**C. Headers**: `Content-Type: application/json`

**D. Request body**

```json
{
  "refresh_token": "<refresh_token_here>"
}
```

| Trường | Kiểu | Bắt buộc | Quy tắc |
|---|---|---:|---|
| `refresh_token` | string | Có | Token chuỗi ngẫu nhiên (opaque token) |

**E. Response mẫu**

```json
{
  "access_token": "<new_access_token>",
  "token_type": "bearer",
  "refresh_token": "<new_refresh_token>"
}
```

HTTP `200 OK`.

**F. Lỗi thường gặp**

- `401`: Refresh token không hợp lệ, đã hết hạn, hoặc đã bị thu hồi/sử dụng trước đó (chống token reuse).

---

### 3.32 Đăng xuất (Logout & Token Revocation)

**Thông tin chung**

- Method: `POST`
- Path: `/api/v1/auth/logout`
- Operation ID: `logout`
- Full URL mẫu: `http://127.0.0.1:8000/api/v1/auth/logout`
- Chức năng: Đăng xuất phiên làm việc; đưa `jti` của access token vào blacklist `RevokedToken` và thu hồi `RefreshToken` tương ứng.
- Module: Auth
- Authentication: Bắt buộc Bearer JWT
- Role/permission: User active
- Content-Type: `application/json` (tuỳ chọn)
- Trạng thái xác minh: **Đã test** — Pytest `test_auth_session.py`.

**A/B. Path và query parameters**: Không có.

**C. Headers**: `Authorization: Bearer <access_token>`, `Content-Type: application/json` (tuỳ chọn)

**D. Request body** (Tuỳ chọn)

```json
{
  "refresh_token": "<refresh_token_to_revoke>"
}
```

**E. Response mẫu**

HTTP `204 No Content`.

**F. Lỗi thường gặp**

- `401`: Access token không hợp lệ, thiếu token, hoặc token đã bị thu hồi trước đó.

---

### 3.33 Yêu cầu quên mật khẩu (Password Recovery Request)

**Thông tin chung**

- Method: `POST`
- Path: `/api/v1/auth/password/forgot`
- Operation ID: `forgot_password`
- Full URL mẫu: `http://127.0.0.1:8000/api/v1/auth/password/forgot`
- Chức năng: Tạo token đặt lại mật khẩu với thời hạn cấu hình; trả về phản hồi generic an toàn để chống dò quét tài khoản người dùng.
- Module: Auth
- Authentication: Không yêu cầu
- Role/permission: Không có
- Content-Type: `application/json`
- Trạng thái xác minh: **Đã test** — Pytest `test_auth_session.py`.

**A/B. Path và query parameters**: Không có.

**C. Headers**: `Content-Type: application/json`

**D. Request body**

```json
{
  "email": "user@example.com"
}
```

**E. Response mẫu**

```json
{
  "message": "Nếu email tồn tại, hướng dẫn đặt lại mật khẩu đã được gửi.",
  "reset_token": "<reset_token_for_test_mode_or_null>"
}
```

HTTP `202 Accepted`.

---

### 3.34 Đặt lại mật khẩu (Password Reset)

**Thông tin chung**

- Method: `POST`
- Path: `/api/v1/auth/password/reset`
- Operation ID: `reset_password`
- Full URL mẫu: `http://127.0.0.1:8000/api/v1/auth/password/reset`
- Chức năng: Xác thực token khôi phục (sử dụng 1 lần), cập nhật mật khẩu mới và tự động vô hiệu hóa toàn bộ refresh token cũ của người dùng.
- Module: Auth
- Authentication: Không yêu cầu
- Role/permission: Không có
- Content-Type: `application/json`
- Trạng thái xác minh: **Đã test** — Pytest `test_auth_session.py`.

**A/B. Path và query parameters**: Không có.

**C. Headers**: `Content-Type: application/json`

**D. Request body**

```json
{
  "token": "<reset_token>",
  "new_password": "NewStrongPassword123"
}
```

**E. Response mẫu**

HTTP `204 No Content`.

**F. Lỗi thường gặp**

- `422`: Token không hợp lệ, token đã được dùng hoặc đã hết hạn. Mật khẩu không đáp ứng độ dài tối thiểu (8 ký tự).

### 3.35 Ghi nhận lượt xem video (Video View Count)

**Thông tin chung**

- Method: `POST`
- Path: `/api/v1/videos/{video_id}/views`
- Operation ID: `record_video_view`
- Full URL mẫu: `http://127.0.0.1:8000/api/v1/videos/<video_id>/views`
- Chức năng: Ghi nhận lượt xem (view count) cho video với cơ chế Cooldown chống spam và gian lận.
- Module: Video Management
- Authentication: Tùy chọn (Hỗ trợ cả Guest và Authenticated User).
- Role/permission: Bất kỳ ai (Khách hoặc Người dùng đã đăng nhập).
- Content-Type: `application/json`
- Trạng thái xác minh: **Đã test** — Pytest `tests/test_video_views.py`.

**A. Path parameters**

- `video_id` (UUID): ID của video được ghi nhận lượt xem.

**B. Query parameters**: Không có.

**C. Headers**: Tùy chọn `Authorization: Bearer <access_token>` nếu người xem đã đăng nhập.

**D. Request body**: Không có.

**E. Cơ chế nghiệp vụ và Cooldown 5 phút (300 giây)**

- **Khóa nhận diện định danh:**
  `view:{video_id}:{user_id if user_id else client_ip}`
- **Quy tắc đếm:**
  + Cùng 1 tài khoản (User ID) hoặc cùng 1 địa chỉ IP (đối với khách chưa đăng nhập) chỉ được ghi nhận tăng lượt xem **tối đa 1 lần mỗi 5 phút (300 giây)** cho cùng một video.
  + Nếu gọi API trong thời gian Cooldown: API trả về HTTP `200` với `"counted": false`, `view_count` giữ nguyên.
  + Nếu gọi API khi đã hết Cooldown (hoặc lần xem đầu tiên): API thực hiện cập nhật nguyên tử (`UPDATE videos SET view_count = view_count + 1 WHERE id = :video_id`), trả về HTTP `200` với `"counted": true`, `view_count` tăng thêm 1.

**F. Contract giao tiếp chi tiết cho Frontend**

Để tối ưu trải nghiệm và ngăn ngừa request dư thừa, Frontend cần tuân thủ nghiêm ngặt các quy tắc sau:

1. **Điều kiện kích hoạt request:**
   - Client **chỉ kích hoạt request** khi video đang ở trạng thái **active** (đang hiển thị trong viewport người dùng và đang phát).
   - Người dùng đã **xem liên tục đủ từ 5 giây trở lên** (`Minimum Watch Duration = 5s`). Sử dụng hook theo dõi `ref` của thẻ `<video>` (`timeupdate` event hoặc timer tích lũy thời gian phát thực tế).
2. **Video ngắn dưới 5 giây:**
   - Nếu video có tổng thời lượng nhỏ hơn 5 giây (ví dụ video 3s - 4s), kích hoạt request khi người dùng **xem hết toàn bộ video** (bắt sự kiện `onEnded`).
3. **Quản lý cờ trạng thái tại Client (Deduplication):**
   - Giữ cờ `hasCountedView = true` trong local state của từng video slide / player item.
   - Khi cờ `hasCountedView === true`, **tuyệt đối không gửi thêm bất kỳ request nào** trong cùng phiên hiển thị video đó, kể cả khi video lặp lại (`loop`).
   - Cờ `hasCountedView` chỉ được khởi tạo lại khi người dùng rời đi và quay trở lại sau đó.

**G. Response mẫu**

Lần đầu xem hợp lệ (tăng view):
```json
{
  "video_id": "76ec9d15-0691-44fe-9337-674e2a220261",
  "view_count": 142,
  "counted": true
}
```

Trường hợp đang trong thời gian Cooldown 5 phút:
```json
{
  "video_id": "76ec9d15-0691-44fe-9337-674e2a220261",
  "view_count": 142,
  "counted": false
}
```

**H. Lỗi thường gặp**

- `404 Not Found`: Video không tồn tại hoặc đã bị xóa mềm (`is_deleted = true`).
- `422 Unprocessable Entity`: `video_id` không đúng định dạng UUID.

**I. Ví dụ gọi cURL**

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/videos/76ec9d15-0691-44fe-9337-674e2a220261/views"
```

---

>>>>>>> 0dcf2c46a0f557080b0fcca8ac5384151d871ffd
## 4. Luồng gọi API thực tế

### 4.1 Tạo user và đọc profile

1. `POST /api/v1/auth/register` với email/display name/password.
2. `POST /api/v1/auth/login` với cùng email/password.
3. Lưu `access_token` trong biến Postman `access_token`.
4. Gửi `GET /api/v1/profile` với
   `Authorization: Bearer {{access_token}}`.

### 4.2 Upload và đọc AI result

1. Login để lấy `access_token`.
2. `POST /api/v1/videos?caption=Demo`, multipart field `file`.
3. Lưu `id` trong response thành `video_id`.
4. Gọi `GET /api/v1/videos/{video_id}/ai`.
5. Nếu NSFW-Detection chạy được, transcript chứa phán quyết `ADULT`/`NORMAL` và
   label tương ứng (`Adult` đưa video vào `pending_review`, `Safe` đăng công khai).
   Nếu môi trường AI chưa sẵn sàng, transcript ghi rõ lý do và kết quả là mock:
   `job_status: "succeeded"`, label `Safe` 0.95. Không coi đây là kết quả AI
   production.

### 4.3 Report và moderation

1. User login.
2. Upload video và lấy `video_id`, hoặc dùng ID video hiện có.
3. Gửi `POST /api/v1/videos/{video_id}/reports`.
4. Moderator/admin login và gửi `GET /api/v1/moderation/queue` hoặc
   `GET /api/v1/moderation/reports`.
5. Lấy `report_id` từ danh sách report mở.
6. Gửi `POST /api/v1/moderation/reports/{report_id}/decision`.
7. Không gửi lại report đã xử lý; implementation trả `404`.

## 5. Bảng tổng hợp endpoint

| STT | Method | Path | Module | Auth | Trạng thái kiểm thử |
|---:|---|---|---|---|---|
| 1 | GET | `/health` | System | Không | Đã test |
| 2 | POST | `/api/v1/auth/register` | Auth | Không | Đã test |
| 3 | POST | `/api/v1/auth/login` | Auth | Không | Đã test |
| 4 | GET | `/api/v1/profile` | User Profile | JWT | Đã test |
| 5 | POST | `/api/v1/videos` | Video Upload | JWT | Đã test |
| 6 | GET | `/api/v1/videos` | Video Management | JWT | Đã test |
| 7 | GET | `/api/v1/feed` | Video Management | Không | Đã test |
| 8 | GET | `/api/v1/videos/search` | Tag Search | Không | Đã test |
| 9 | GET | `/api/v1/search/videos-by-tag/grid` | Tag Search | Không | Code/OpenAPI |
| 10 | GET | `/api/v1/videos/{video_id}/ai` | AI Analysis | JWT + owner/mod/admin | Đã test |
| 11 | PATCH | `/api/v1/videos/{video_id}` | Video Management | JWT + owner | Đã test |
| 12 | GET | `/api/v1/videos/{video_id}/labels` | Label Management | Không/optional JWT | Code/OpenAPI |
| 13 | POST | `/api/v1/videos/{video_id}/labels/confirm` | Label Management | JWT + owner | Đã test |
| 14 | DELETE | `/api/v1/videos/{video_id}` | Video Management | JWT + owner | Đã test |
| 15 | POST | `/api/v1/videos/{video_id}/reports` | Content Report | JWT | Đã test |
| 16 | GET | `/api/v1/videos/{video_id}/comments` | Social Interactions | JWT | Đã test |
| 17 | POST | `/api/v1/videos/{video_id}/comments` | Social Interactions | JWT | Đã test |
| 18 | GET | `/api/v1/moderation/queue` | Moderation | JWT + mod/admin | Đã test |
| 19 | POST | `/api/v1/moderation/videos/{video_id}/decision` | Moderation | JWT + mod/admin | Code/OpenAPI |
| 20 | GET | `/api/v1/moderation/reports` | Moderation | JWT + mod/admin | Đã test |
| 21 | POST | `/api/v1/moderation/reports/{report_id}/decision` | Moderation | JWT + mod/admin | Đã test |
| 22 | GET | `/api/v1/admin/users` | Admin Management | JWT + admin | Đã test |
| 23 | GET | `/api/v1/admin/users/{user_id}` | Admin Management | JWT + admin | Đã test |
| 24 | PATCH | `/api/v1/admin/users/{user_id}/status` | Admin Management | JWT + admin | Đã test |
| 25 | GET | `/api/v1/admin/moderators` | Admin Management | JWT + admin | Đã test |
| 26 | PATCH | `/api/v1/admin/users/{user_id}/role` | Admin Management | JWT + admin | Đã test |
| 27 | GET | `/api/v1/videos/{video_id}/stream` | Video Management | Không (JWT nếu chưa published) | Đã test |
<<<<<<< HEAD
=======
| 28 | POST | `/api/v1/videos/{video_id}/appeals` | Appeals / Re-review | JWT + owner | Đã test |
| 29 | GET | `/api/v1/moderation/appeals` | Moderation Appeals | JWT + mod/admin | Đã test |
| 30 | POST | `/api/v1/moderation/appeals/{appeal_id}/decision` | Moderation Appeals | JWT + mod/admin | Đã test |
| 31 | PATCH | `/api/v1/videos/{video_id}/labels` | Label Management | JWT + mod/admin | Đã test |
| 32 | POST | `/api/v1/admin/labels` | Label Administration | JWT + admin | Đã test |
| 33 | GET | `/api/v1/admin/labels` | Label Administration | JWT + admin | Đã test |
| 34 | PATCH | `/api/v1/admin/labels/{label_id}` | Label Administration | JWT + admin | Đã test |
| 35 | PATCH | `/api/v1/admin/videos/{video_id}/status` | Video Administration | JWT + admin | Đã test |
| 36 | GET | `/api/v1/admin/stats` | System Statistics | JWT + admin | Đã test |
| 37 | GET | `/api/v1/admin/moderators/{moderator_id}/stats` | Moderator Statistics | JWT + admin | Đã test |
| 38 | POST | `/api/v1/auth/refresh` | Auth | Không | Đã test |
| 39 | POST | `/api/v1/auth/logout` | Auth | JWT | Đã test |
| 40 | POST | `/api/v1/auth/password/forgot` | Auth | Không | Đã test |
| 41 | POST | `/api/v1/auth/password/reset` | Auth | Không | Đã test |
| 42 | POST | `/api/v1/videos/{video_id}/views` | Video Management | Tùy chọn (JWT/IP) | Đã test |
>>>>>>> 0dcf2c46a0f557080b0fcca8ac5384151d871ffd

## 6. Đối chiếu và giới hạn

- OpenAPI runtime sau thay đổi bao gồm Feed cursor, tag search grid, video edit,
  labels, social interactions và R2 redirect stream như các mục trên.
- Không có router khác được đăng ký trong application hiện tại.
- Feed và tag search dùng cursor pagination; các endpoint list khác chưa có
  pagination/search/filter chung.
- File video chỉ lấy được qua endpoint stream; `storage_path` không
  được trả ra trong `VideoResponse`.
<<<<<<< HEAD
- Không có logout, token revocation, refresh token hoặc password recovery.
=======
- Đã hoàn tất hỗ trợ đầy đủ cơ chế logout, thu hồi token (blacklist JTI), xoay vòng refresh token và quy trình khôi phục mật khẩu (password recovery).
>>>>>>> 0dcf2c46a0f557080b0fcca8ac5384151d871ffd
- `PATCH /api/v1/videos/{video_id}` không cho phép đổi file, view count, like
  count hoặc audit data.
- Endpoint quyết định video moderation đã đối chiếu source/OpenAPI nhưng chưa có
  request Newman riêng; vì vậy được đánh dấu `Code/OpenAPI`, không đánh dấu
  `Đã test`.
- Các response ví dụ UUID/thời gian là placeholder an toàn, trừ các giá trị
  mock AI và status đã được xác minh trong test local.
- Không đưa password, JWT thật, secret, API key, connection string hoặc dữ liệu
  cá nhân vào tài liệu.

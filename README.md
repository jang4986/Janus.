# PBL6 — AI Short Video Moderation Platform

PBL6 is a Vite/React frontend and FastAPI backend for a short-video platform
with JWT authentication, local video storage, AI content analysis, user
reports, and moderation workflows.

AI analysis is integrated with the local `NSFW-Detection` pipeline (Adult
detection, TensorFlow + PyTorch) through a subprocess adapter. While the AI
environment is not installed, the job records why and falls back to the mock
result instead of failing. Violence, sound and text/STT detection are still
detector placeholders, so the code never pretends to be complete.

The frontend is now located under `frontend/`. Cloud object storage and
production-grade moderation infrastructure are not included in the current
repository.

## Contents

- [Overview](#overview)
- [Current capabilities](#current-capabilities)
- [Architecture](#architecture)
- [Technology stack](#technology-stack)
- [Repository structure](#repository-structure)
- [Prerequisites](#prerequisites)
- [Hướng dẫn cài đặt & Khởi chạy dự án (1-Click Dev)](#hướng-dẫn-cài-đặt--khởi-chạy-dự-án-1-click-dev)
- [Local setup](#local-setup)
- [Running the backend](#running-the-backend)
- [Database and migrations](#database-and-migrations)
- [Testing](#testing)
- [API documentation](#api-documentation)
- [Project status and limitations](#project-status-and-limitations)
- [Development workflow](#development-workflow)
- [Security and data-safety notes](#security-and-data-safety-notes)

## Overview

The system supports a moderation-oriented video workflow:

1. A user registers and signs in.
2. The authenticated user uploads an MP4 video.
3. The backend validates the file and stores it locally.
4. A background analysis task runs the NSFW-Detection pipeline and stores the
   resulting label and confidence. Videos with a risk label enter the
   moderation queue.
5. Published videos are available through the public feed.
6. Users can report videos.
7. Moderators and admins can review queues and make moderation decisions.
8. Admins can manage user status and the roles supported by the current model.

The AI entry point is `run_video_analysis` in
[backend/src/app/services/ai_service.py](backend/src/app/services/ai_service.py),
which calls `app.ai.pipeline.analyse_video`. The Adult detector shells out to
`backend/NSFW-Detection/src/proposed/proposed_adult_video_detect.py` and reads its
`08_final_decision.json` output; no external AI API or Cloud Storage is used.

## Current capabilities

### Implemented and tested

- User registration and JWT login.
- Authenticated profile retrieval.
- Role model with `user`, `moderator`, and `admin`.
- MP4 upload with:
  - `.mp4` filename and `video/mp4` MIME validation.
  - 50 MiB size limit.
  - MP4 `ftyp`/brand/codec validation.
  - Local filesystem storage.
- AI content analysis (`run_video_analysis` → `app.ai.pipeline`):
  - Adult detection runs the NSFW-Detection pipeline in a subprocess and reads
    its `08_final_decision.json` result.
  - `AI_ANALYSIS_MODE=auto` (default): if the AI environment is unavailable the
    job records the reason in the transcript and falls back to the mock result.
  - `AI_ANALYSIS_MODE=required`: the job is marked `failed` when the AI
    environment is unavailable; `off` keeps the old mock-only behaviour.
  - A detected risk label (`Adult`) moves the video to `pending_review`; a
    normal result publishes it with a `Safe` label and its confidence.
  - Mock fallback result: development transcript, `Safe` label, confidence
    `0.95`, level `HIGH`.
- User video listing, public feed, and owner-only soft delete.
- Content reports with validation and duplicate-open-report protection.
- Moderation queue, open-report list, and moderation decisions.
- Admin MVP:
  - User list and search.
  - User detail.
  - Activate/deactivate user.
  - Moderator/admin list.
  - Role changes for the enum values supported by the model.
- Session management (UC001–UC002):
  - Refresh tokens with rotation (`POST /api/v1/auth/refresh`).
  - Logout revoking the current access token (`jti`) and, when supplied, the
    paired refresh token (`POST /api/v1/auth/logout`).
  - Password reset tokens (`forgot`/`reset`, 30 minutes, single use). Because
    no mail provider is integrated, `reset_token` is only echoed in the
    response when `environment` is not `production`.
- Profile update (`PATCH /api/v1/profile`): display name and password change;
  a password change revokes every refresh token.
- Video playback `GET /api/v1/videos/{id}/stream` with HTTP Range support.
- Label search `GET /api/v1/videos/search` (`label`, `exclude_label`, `q`,
  `limit`) returning each video's labels and owner.
- Label confirmation/editing: owner `POST /videos/{id}/labels/confirm`,
  moderator/admin `PATCH /videos/{id}/labels` (multi-label replace).
- Appeals (UC011/UC017): create, moderated list, approve/reject decision; an
  approved appeal publishes the video again. One open appeal per
  (video, user) is enforced by a partial unique index.
- Admin label management (2.2.13): list, create, rename, activate/deactivate,
  with video counts.
- Admin video status (2.2.12): publish, re-review, reject or soft-delete.
- Statistics (UC019/UC020): per-moderator counters and a `days`-window
  dashboard (videos by status, label distribution, reports/appeals/jobs,
  moderator workload).

### Partially implemented

- Moderation has no locking/claim workflow or complete audit history.
- Admin management does not yet include Senior Moderator, notifications,
  audit logs, workload statistics, or locked-work reassignment.
- Password reset has no mail delivery: outside `production` the reset token is
  returned in the response so the flow can be exercised locally.
- List endpoints have no pagination; only `/videos/search` caps results with
  `limit`.

### Detector placeholders

Detector placeholders (they raise `DetectorNotImplementedError` when called and
are recorded in the job transcript as skipped) live in
[backend/src/app/ai/placeholders.py](backend/src/app/ai/placeholders.py), with empty
model directories under `backend/NSFW-Detection/src/models/{violence,sound,text}/`.

### Not implemented in the current repository

- Frontend application.
- Speech-to-Text and the violence, sound and text detectors (placeholders only).
- Cloud video storage and email delivery for password reset.
- Pagination/filtering for the feed, video, report and moderation-queue lists.
- Moderation claim/locking, a full audit log, notifications and a job queue.

These status statements describe the current codebase, not a promise that the
corresponding SRS use cases are complete.

## Architecture

```mermaid
flowchart LR
    Client[Postman / API client] --> API[FastAPI application]
    API --> Auth[JWT and RBAC]
    API --> ORM[SQLAlchemy]
    ORM --> DB[(Neon PostgreSQL)]
    API --> Storage[Local upload directory]
    API --> Task[FastAPI BackgroundTasks]
    Task --> AI[run_video_analysis]
    AI --> Pipeline[app.ai.pipeline]
    Pipeline --> NSFW[NSFW-Detection subprocess]
    Pipeline --> Fallback[Mock fallback]
    NSFW --> ORM
    Fallback --> ORM
```

The test fixture uses a separate SQLite database and `test_storage`
directory so the test suite does not require destructive operations against the
online Neon database. The running backend reads `DATABASE_URL` from
`backend/.env`, which is filled in from `local/neondb.txt`.

## Technology stack

| Area | Technology verified in the repository |
|---|---|
| Language/runtime | Python; the development environment used Python 3.12 |
| API | FastAPI |
| Server | Uvicorn |
| Validation/settings | Pydantic and `pydantic-settings` |
| ORM | SQLAlchemy 2.x |
| Database | Neon PostgreSQL (online) with `psycopg[binary]`; URL from `local/neondb.txt` |
| Migrations | Alembic |
| Authentication | PyJWT and `hashlib.scrypt` password hashing |
| Background processing | FastAPI `BackgroundTasks` |
| AI content analysis | NSFW-Detection pipeline (TensorFlow 2.20 + PyTorch 2.6) run as a subprocess |
| Automated tests | Pytest and FastAPI TestClient |
| API collections | Postman/Newman local collections |

Backend dependency ranges are maintained in
[backend/pyproject.toml](backend/pyproject.toml) and resolved in
`backend/uv.lock`; `uv sync` creates `backend/.venv`. AI dependencies
are maintained in the separate
[backend/NSFW-Detection/src/pyproject.toml](backend/NSFW-Detection/src/pyproject.toml)
and its `uv.lock`, so the API environment stays small.

## Repository structure

```text
.
├── backend/                      # Backend (FastAPI) — uv project của Python
│   ├── pyproject.toml         # [project] deps + dev group + cấu hình pytest
│   ├── uv.lock                # Lockfile Python (uv sync)
│   ├── .venv/                 # Môi trường ảo do uv tạo (bị Git bỏ qua)
│   ├── src/app/               # Gói ứng dụng, cài editable nên `import app` chạy được
│   │   ├── api/v1/            # router + endpoints theo tài nguyên
│   │   ├── core/              # config.py (settings), security.py (JWT/scrypt)
│   │   ├── db/                # session.py (engine, SessionLocal, Base)
│   │   ├── models/            # entity SQLAlchemy và enum
│   │   ├── schemas/           # Pydantic request/response
│   │   ├── services/          # nghiệp vụ (ai_service, auth_service, ...)
│   │   ├── ai/                # base.py, nsfw.py, pipeline.py, placeholders.py
│   │   ├── dependencies.py    # JWT authentication and RBAC dependencies
│   │   ├── exceptions.py      # ServiceError và lỗi nghiệp vụ
│   │   └── main.py            # FastAPI application and route handlers
│   ├── NSFW-Detection/
│   │   └── src/
│   │       ├── proposed/      # Adult detection pipeline (4 stages)
│   │       ├── models/        # Adult models + {violence,sound,text}/ placeholders
│   │       ├── pyproject.toml    # AI dependencies managed by uv
│   │       ├── uv.lock           # AI dependency lockfile
│   │       └── README.md      # Pipeline usage, configuration, benchmarks
│   ├── alembic/versions/      # Database migrations
│   ├── scripts/check_db.py    # Non-destructive database connectivity check
│   ├── tests/                 # Official Pytest suite
│   ├── .env.example           # Safe configuration template (.env is ignored)
│   └── alembic.ini
├── frontend/                  # Vite/React frontend and npm lockfile
├── local/                     # Toàn bộ bị Git bỏ qua
│   ├── SRS.docx               # Tài liệu yêu cầu chính thức
│   ├── neondb.txt             # Chuỗi kết nối Neon PostgreSQL
│   └── TestDataset-v2/        # Bộ video test (Adult/, Normal/)
├── local-tests/               # Postman collections và module log (bị Git bỏ qua)
├── API_ENDPOINTS_GUIDE.md     # Detailed endpoint integration guide (legacy)
├── docs/                      # Tài liệu: API, database, testing, kiến trúc
├── README.md
└── .gitignore
```

`local/` is ignored as a whole, so `SRS.docx`, `neondb.txt` and
`TestDataset-v2/` can never be committed by accident. Postman collections,
module logs under `local-tests/`, runtime data and secrets are excluded from
Git as well.

## Prerequisites

Install or make available:

- Python 3.12 or another interpreter accepted by `pyproject.toml`.
- `uv` for Python environments and dependencies.
- Node.js and npm for the frontend.
- Access to the Neon PostgreSQL connection string stored in `local/neondb.txt`.
- Optional — only to run the real Adult pipeline: the separate uv project at
  `backend/NSFW-Detection/src`, selected via `NSFW_PYTHON` when needed.
- Git.
- Newman if API collection tests are required.

PowerShell is used in the examples below. Do not use production credentials or
production databases for local development or tests.

## Hướng dẫn cài đặt & Khởi chạy dự án (1-Click Dev)

Dự án cung cấp bộ script tự động hóa khởi chạy toàn bộ hệ thống (Backend + Frontend) chỉ với **1 lệnh duy nhất** trên cả Windows, Linux và macOS.

### 1. Khởi chạy nhanh theo Hệ điều hành

#### Windows
- **Cách 1 (PowerShell):**
  ```powershell
  .\run_dev.ps1
  ```
- **Cách 2 (Batch script tiện ích):**
  Nhấp đúp chuột vào file `run_dev.bat` trong thư mục gốc dự án.

#### Linux / macOS
- **Cấp quyền thực thi lần đầu:**
  ```bash
  chmod +x run_dev.sh
  ```
- **Khởi chạy:**
  ```bash
  ./run_dev.sh
  ```

### 2. Các hành động tự động hóa mà script thực hiện ngầm
- **Kiểm tra công cụ môi trường:** Xác nhận sự hiện diện của `uv`, `node` và `npm`.
- **Tự động đồng bộ thư viện Backend (`uv sync`):** Cập nhật toàn bộ dependencies Python từ `pyproject.toml` và `uv.lock`.
- **Tự động kiểm tra & cài đặt dependencies Frontend:** Tự kiểm tra `frontend/node_modules` và chạy `npm --prefix frontend install` nếu chưa có.
- **Tự động chạy migration Database (Alembic):** Luôn tự động thực thi `uv run --directory backend alembic upgrade head` để đảm bảo cơ sở dữ liệu luôn ở phiên bản mới nhất trước khi server chạy. Nếu migration lỗi, script dừng ngay lập tức để tránh lỗi runtime.
- **Khởi chạy song song Backend & Frontend:** Chạy song song Uvicorn (FastAPI) trên cổng `8000` và Vite (React) trên cổng `5173`.
- **Tự động dọn dẹp sạch tiến trình & port khi thoát (`Ctrl + C`):** Bắt sự kiện thoát (SIGINT / finally), tự động đóng toàn bộ tiến trình con và giải phóng cổng `8000` cùng `5173`, chống kẹt port triệt để.

### 3. Bảng URL truy cập mặc định

| Dịch vụ | Địa chỉ URL | Mô tả |
|---|---|---|
| **Frontend** | `http://localhost:5173` | Giao diện web người dùng (Vite + React) |
| **Backend API** | `http://127.0.0.1:8000` | Dịch vụ API Backend (FastAPI) |
| **Swagger Docs** | `http://127.0.0.1:8000/docs` | Tài liệu tương tác API OpenAPI / Swagger UI |

---

## Local setup

### 1. Clone and create the uv environment

```powershell
git clone https://github.com/Hrk9324/PBL6_AI_short_video_moderation.git
Set-Location PBL6_AI_short_video_moderation

cd backend
uv sync
```

`uv` tự tạo `backend\.venv` và `backend\uv.lock` (nguồn phiên bản đã resolve).
Không activates `.venv` bằng tay và không cài dependency vào một `backend\.venv`
tách biệt: mọi lệnh backend đều chạy qua `uv run` từ thư mục `backend\` (hoặc từ
gốc repo với `uv run --directory backend ...`).

## Cấu trúc thư mục

```text
.
├── backend/            # Dự án uv của backend (FastAPI), layout src/
│   ├── pyproject.toml  # [project] deps + dev group + pytest pythonpath = src
│   ├── uv.lock         # Lockfile Python (uv sync)
│   ├── .venv/          # Môi trường ảo do uv tạo (không commit)
│   ├── src/app/
│   │   ├── api/v1/     # router + endpoints theo tài nguyên
│   │   ├── core/       # config, security
│   │   ├── db/         # session, engine, Base
│   │   ├── models/     # entity SQLAlchemy
│   │   ├── schemas/    # Pydantic request/response
│   │   ├── services/   # nghiệp vụ
│   │   ├── ai/         # pipeline NSFW + detector placeholder
│   │   ├── dependencies.py, exceptions.py, main.py
│   ├── tests/          # pytest
│   ├── alembic/        # migration
│   └── scripts/        # check_db.py kiểm tra kết nối DB
├── frontend/           # Vite + React
│   └── src/
│       ├── app/        # App, routes, guards, layout
│       ├── pages/      # trang được định tuyến
│       ├── features/   # auth, videos, moderation (api + hooks + components)
│       ├── shared/     # api client, component, lib dùng chung
│       └── styles/     # CSS theo khu vực
├── docs/               # tài liệu, báo cáo dự án
└── local/, local-tests/   # dữ liệu và log cục bộ (không commit)
```

## Chạy frontend và kết nối backend

> [!TIP]
> **Khuyên dùng:** Bạn có thể khởi chạy nhanh toàn bộ hệ thống bằng 1 click thông qua các script `run_dev.bat` / `run_dev.ps1` (Windows) hoặc `run_dev.sh` (Linux/macOS) đã được thiết lập sẵn ở thư mục gốc (xem chi tiết tại mục [Hướng dẫn cài đặt & Khởi chạy dự án](#hướng-dẫn-cài-đặt--khởi-chạy-dự-án-1-click-dev)). Nếu muốn chạy thủ công từng phần độc lập bằng 2 terminal riêng biệt, thực hiện như sau:

Backend (cửa sổ 1):

```powershell
cd E:\PBL6\backend
uv sync                       # chỉ chạy lần đầu (hoặc khi đổi dependencies)
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000   # http://127.0.0.1:8000
```

Frontend (cửa sổ 2):

```powershell
cd E:\PBL6\frontend
npm install
npm run dev                                   # http://localhost:5173
```

Cách hai bên nối với nhau:

- Chế độ dev: Vite proxy mọi request `/api` sang `http://127.0.0.1:8000`, nên
  trình duyệt gọi cùng origin và không cần CORS. Đổi đích bằng biến
  `VITE_API_PROXY_TARGET`.
- Chế độ production: đặt `VITE_API_BASE_URL` (frontend) trỏ tới origin backend
  và khai báo origin frontend trong `CORS_ORIGINS` (backend, mặc định
  `http://localhost:5173,http://127.0.0.1:5173`).
- Luồng đã kết nối: đăng ký/đăng nhập lấy JWT → `POST /api/v1/videos` tải video
  → poll `GET /api/v1/videos/{id}/ai` tới khi job xong → feed phát video qua
  `GET /api/v1/videos/{id}/stream` → báo cáo đưa video vào hàng đợi kiểm duyệt.

## Thiết lập database

Backend đọc `DATABASE_URL` từ `backend\.env`. Có hai lựa chọn:

- **Neon PostgreSQL (mặc định)** — không cần cài gì thêm, chỉ cần chuỗi kết nối
  trong `local/neondb.txt` → làm **bước 1** rồi nhảy tới **bước 4**.
- **PostgreSQL cục bộ trên Windows 10/11** — cho máy không dùng Neon → làm đủ
  **bước 2 đến bước 5**.

Các lệnh dùng PowerShell và không yêu cầu gửi mật khẩu thật trong cuộc trò
chuyện.

### 1. Database: online Neon PostgreSQL

The Docker Compose PostgreSQL service has been removed from this repository.
The backend connects to the online Neon database described by
`local/neondb.txt`; the whole `local/` directory is ignored by Git.

No local database process is required. `backend/scripts/check_db.py` is a
non-destructive way to verify the connection:

```powershell
Set-Location backend
uv run python -m scripts.check_db
```

Expected output includes `database=neondb` and `user=neondb_owner`.

### 2. Kiểm tra PostgreSQL cục bộ (bỏ qua nếu dùng Neon)

Mở PowerShell mới, kiểm tra service/host/port; nếu service đã cài mà chưa chạy
thì khởi động trước:

```powershell
Get-Service -Name "postgresql*" | Format-Table Name,Status,StartType
Start-Service -Name "postgresql-x64-16" # thay tên bằng kết quả thực tế
```

Nếu service đã chạy, không cần gọi `Start-Service`. Host mặc định là
`localhost`, port là `5432`, còn database/role sẽ được tạo ở bước 3.
Có thể dùng `psql` hoặc pgAdmin để thực hiện các câu lệnh SQL.

```powershell
Test-NetConnection localhost -Port 5432
```

### 3. Tạo database và role ứng dụng (bỏ qua nếu dùng Neon)

Đăng nhập bằng role quản trị cục bộ. Thay `postgres` bằng role quản trị của
bạn nếu đã chọn tên khác:

```powershell
psql -h localhost -p 5432 -U postgres -d postgres
```

Trong cửa sổ `psql`, thay các giá trị mẫu bằng mật khẩu riêng của bạn. Không
đưa mật khẩu thật vào README, script hoặc Git:

```sql
CREATE ROLE pbl6_app WITH LOGIN PASSWORD 'CHANGE_ME_TO_A_PRIVATE_PASSWORD';
CREATE DATABASE pbl6 OWNER pbl6_app;
\c pbl6
GRANT CONNECT ON DATABASE pbl6 TO pbl6_app;
GRANT USAGE, CREATE ON SCHEMA public TO pbl6_app;
\du pbl6_app
\l pbl6
\q
```

Role `pbl6_app` chỉ phục vụ Backend; không dùng role superuser `postgres` cho
ứng dụng trong môi trường thông thường. Nếu database hoặc role đã tồn tại,
không chạy lại lệnh tạo một cách mù quáng; kiểm tra trước:

```powershell
psql -h localhost -p 5432 -U postgres -d postgres -c "\du"
psql -h localhost -p 5432 -U postgres -d postgres -c "\l"
```

Kiểm tra quyền bằng tài khoản ứng dụng:

```powershell
psql -h localhost -p 5432 -U pbl6_app -d pbl6 -c "SELECT current_user, current_database(), version();"
```

Backend cũng có thể kiểm tra kết nối mà không in mật khẩu:

```powershell
cd E:\PBL6\backend
uv run python -m scripts.check_db
```

### 4. Cấu hình `.env`

Từ thư mục `E:\PBL6\backend`:

```powershell
Copy-Item .env.example .env
```

Edit `.env` with local values. Copy `DATABASE_URL` from `local/neondb.txt`;
the safe template contains:

```dotenv
# Lấy từ local/neondb.txt — không commit file này
DATABASE_URL=postgresql://USER:PASSWORD@ep-xxxx.aws.neon.tech/neondb?sslmode=require
SECRET_KEY=replace-with-a-long-random-development-secret-key
UPLOAD_DIR=storage/uploads
MAX_UPLOAD_SIZE_BYTES=52428800

# Chế độ phân tích AI: auto | required | off
AI_ANALYSIS_MODE=auto
# Interpreter chạy pipeline NSFW-Detection (TF 2.20 cần Python 3.11)
NSFW_PYTHON=
# Thư mục này tương đối so với backend/
NSFW_PIPELINE_DIR=NSFW-Detection/src
NSFW_TIMEOUT_SECONDS=600
```

Use URL encoding for reserved characters in a connection URL password. Never
commit `.env`, `local/neondb.txt` or share real credentials. The application reads
settings from the backend working directory.

### 5. Apply migrations

```powershell
Set-Location backend
uv run alembic current
uv run alembic upgrade head
uv run alembic current
```

Migrations are `0001_initial` (users, videos, labels, video labels, AI jobs,
moderation reviews, reports) and `0002_session_appeals` (refresh tokens,
revoked access tokens, password reset tokens, appeals). Both are already
applied to the Neon database in this workspace, so `alembic current` must
report `0002_session_appeals (head)`.

Do not drop or reset a database to resolve a migration problem. Check the
database URL, role permissions, schema, and current Alembic revision first.

## Running the backendFrom the repository root:

```powershell
uv run --directory backend uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

hoặc từ thư mục `backend/` (kết quả giống nhau):

```powershell
cd backend
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Run the frontend in a second terminal:

```powershell
Set-Location frontend
npm run dev
```

### Kiểm tra end-to-end và chạy Backend

Thực hiện theo thứ tự:

```powershell
Get-Service -Name "postgresql*" | Where-Object Status -eq "Running"
Test-NetConnection localhost -Port 5432
psql -h localhost -p 5432 -U pbl6_app -d pbl6 -c "SELECT 1;"
uv run alembic current
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Trong PowerShell khác:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Expected response:

```json
{"status": "ok"}
```

FastAPI's generated documentation is available at
<http://127.0.0.1:8000/docs> while the server is running. The OpenAPI JSON is
available at <http://127.0.0.1:8000/openapi.json>.

## Testing

The current verification workflow does not use Pytest. Use Newman against the
running backend and the independent AI smoke command documented in
[docs/TESTING.md](docs/TESTING.md). Existing Pytest files are retained as
repository history, but their results are not evidence for the current
functional status.

The retained suite still runs from `backend/`:

```powershell
cd backend
uv run pytest
```

At the time of writing it reports **15 passed, 20 failed, 8 errors**: the
failures are endpoints that the `src/` refactor has not re-registered yet
(refresh/logout/password reset, `PATCH /profile`, label confirmation/editing,
appeals, `/videos/search`, admin labels and statistics), and the 8 errors come
from the local dataset `local/TestDataset-v2/` not being present.

### Newman

Newman collections are local-only and ignored by Git. With the backend running
on a local port, run a collection such as:

```powershell
Set-Location ..
newman run .\local-tests\postman\auth-jwt_v1.0.0.postman_collection.json `
  --env-var "base_url=http://127.0.0.1:8000"
```

Collections exist for Auth/JWT, User Profile, Video Upload, Video Management,
real AI integration, Content Report, Moderation, and Admin Management. Their
detailed logs remain under `local-tests/logs/` and must not be committed.

Verified local Newman results recorded in the module logs include:

| Collection | Result |
|---|---|
| Auth/JWT | 7 requests, 10 assertions, 0 failed |
| User Profile | 5 requests, 5 assertions, 0 failed |
| Video Upload | 6 requests, 6 assertions, 0 failed |
| Video Management | 10 requests, 10 assertions, 0 failed |
| AI Analysis | 9 requests, 9 assertions, 0 failed |
| Content Report | 8 requests, 8 assertions, 0 failed |
| Moderation | 11 requests, 11 assertions, 0 failed |
| Admin Management | 11 requests, 11 assertions, 0 failed |

These results are historical local evidence recorded in module logs, not a CI
badge or a guarantee for every future environment.

## API documentation

See [docs/API_GUIDE.md](docs/API_GUIDE.md) for the current API guide. The
older [API_ENDPOINTS_GUIDE.md](API_ENDPOINTS_GUIDE.md) is retained as a
historical/source reference and should not be used when it conflicts with the
current guide. The current guide includes:

- All registered endpoints and operation IDs.
- Authentication and role requirements.
- JSON, query, path, and multipart request formats.
- Upload rules and local storage behavior.
- Response examples and implementation-backed errors.
- Postman/cURL examples and workflow sequences.
- A distinction between runtime-tested and source/OpenAPI-only behavior.

## Documentation map

- [docs/USER_GUIDE.md](docs/USER_GUIDE.md): setup and user workflows.
- [docs/API_GUIDE.md](docs/API_GUIDE.md): endpoint contract and examples.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): runtime components and flows.
- [docs/DATABASE.md](docs/DATABASE.md): Neon, migrations, and data safety.
- [docs/AI_MODEL.md](docs/AI_MODEL.md): real model loading and limitations.
- [docs/TESTING.md](docs/TESTING.md): Newman and independent AI checks.
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md): confirmed diagnostics.
- [docs/README.md](docs/README.md): documentation index and status.

## Project status and limitations

The repository is a working backend MVP, not a complete production platform.
The main known limitations are:

- The frontend is present under `frontend/`, but its coverage of the full SRS
  user/moderation workflows is still incomplete.
- The Adult pipeline only runs when its own Python environment (TensorFlow,
  PyTorch, OpenCV) is installed and selected with `NSFW_PYTHON`; otherwise the
  job records the reason in its transcript and falls back to the mock result.
- Speech-to-text and the violence, sound and text detectors are placeholders
  (`DetectorNotImplementedError`) with empty model directories.
- Uploads are local filesystem files; there is no cloud storage adapter, and
  password reset has no mail delivery (the token is echoed only outside
  `production`).
- Feed, report and moderation-queue lists have no pagination; only
  `/videos/search` accepts `limit`.
- Moderation lacks robust locking, concurrency handling, evidence management,
  and a complete audit log.
- Notifications and production job queues are absent; statistics cover the
  requested `days` window only.
- Admin management lacks Senior Moderator, notification, session-revocation
  and locked-work reassignment behavior.
- Schema changes go through reviewed Alembic migrations (currently
  `0002_session_appeals`).
- The `src/` refactor has not re-registered every endpoint listed above:
  the running app exposes 19 routes, so refresh/logout/password reset,
  `PATCH /api/v1/profile`, label confirmation/editing, appeals,
  `/api/v1/videos/search`, admin label management and statistics currently
  answer 404 and their tests fail.

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/profile`
- `POST /api/v1/videos`
- `GET /api/v1/videos`
- `GET /api/v1/feed`
- `GET /api/v1/videos/{video_id}/stream`
- `GET /api/v1/videos/{video_id}/ai`
- `DELETE /api/v1/videos/{video_id}`
- `POST /api/v1/videos/{video_id}/reports`
- `GET /api/v1/moderation/queue`
- `POST /api/v1/moderation/videos/{video_id}/decision`
- `GET /api/v1/moderation/reports`
- `POST /api/v1/moderation/reports/{report_id}/decision`

## Development workflow

Before changing behavior:

1. Read the local project instructions in [local/AGENTS.md](local/AGENTS.md),
   the relevant SRS section, and
   [API_ENDPOINTS_GUIDE.md](API_ENDPOINTS_GUIDE.md).
2. Inspect the existing route, schema, model, dependency, migration, and test.
3. Make a focused change without overwriting unrelated working-tree changes.
4. Run the corresponding local Newman collection or independent script.
6. Record module test history under the ignored local log directory.
7. Update the API guide when the public contract changes.
8. Review `git diff`, `git diff --check`, and staged file names before any
   explicitly authorized commit.

Every new module requires explicit user approval before implementation. Do not
automatically select or start the next module after completing one.

## Security and data-safety notes

- Never commit `.env`, `local/neondb.txt`, passwords, JWTs, API keys, database
  dumps, local media, Postman environments, or runtime logs.
- Do not use production credentials or a production database for local tests.
- The Neon connection string in `local/neondb.txt` is a secret: keep it out of
  Git, chat logs and screenshots (`local/` is ignored as a whole).
- Do not reset, drop, truncate, or delete a database to fix a connection or
  migration issue.
- Keep the SRS and internal development artifacts local.
- Review `.gitignore` and `git status --short` before committing.
- This line trust for check a bug

## License and team

No license or team metadata has been confirmed in the repository. No license
statement is made here.

#!/usr/bin/env bash
set -e

# Chuyển về thư mục chứa script (gốc dự án)
cd "$(dirname "$0")"

echo "=========================================================="
echo "  PBL6 AI SHORT VIDEO MODERATION - 1-CLICK DEV RUNNER     "
echo "=========================================================="

# 1. Kiểm tra môi trường hệ thống
echo "[1/5] Kiểm tra công cụ hệ thống (uv, node, npm)..."
if ! command -v uv >/dev/null 2>&1; then
    echo -e "\033[0;31m[ERROR] 'uv' chưa được cài đặt! Vui lòng cài đặt: https://docs.astral.sh/uv/\033[0m"
    exit 1
fi

if ! command -v node >/dev/null 2>&1; then
    echo -e "\033[0;31m[ERROR] 'node' chưa được cài đặt! Vui lòng cài đặt Node.js.\033[0m"
    exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
    echo -e "\033[0;31m[ERROR] 'npm' chưa được cài đặt! Vui lòng cài đặt npm.\033[0m"
    exit 1
fi
echo -e "\033[0;32m[OK] Môi trường uv, node, npm đã sẵn sàng!\033[0m"

# 2. Đồng bộ dependencies Backend
echo "[2/5] Đồng bộ thư viện Backend (uv sync)..."
uv sync --directory backend
echo -e "\033[0;32m[OK] Thư viện Backend đã được đồng bộ hoàn tất!\033[0m"

# 3. Kiểm tra dependencies Frontend
echo "[3/5] Kiểm tra dependencies Frontend..."
if [ ! -d "frontend/node_modules" ]; then
    echo "[*] Chưa tìm thấy frontend/node_modules. Đang cài đặt..."
    npm --prefix frontend install
    echo -e "\033[0;32m[OK] Cài đặt dependencies frontend hoàn tất!\033[0m"
else
    echo -e "\033[0;32m[OK] frontend/node_modules đã sẵn sàng!\033[0m"
fi

# 4. Đồng bộ Database (Alembic migration)
echo "[4/5] Đồng bộ Database lên bản mới nhất (Alembic migration)..."
uv run --directory backend alembic upgrade head
echo -e "\033[0;32m[OK] Database đã được đồng bộ lên bản mới nhất!\033[0m"

# 5. Khởi động song song Backend và Frontend
echo "[5/5] Khởi động song song Backend và Frontend..."

# Giải phóng cổng nếu còn tiến trình treo từ lần chạy trước
if command -v lsof >/dev/null 2>&1; then
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
    lsof -ti:5173 | xargs kill -9 2>/dev/null || true
fi

# Bật Backend
uv run --directory backend uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

# Bật Frontend
npm run --prefix frontend dev -- --host 127.0.0.1 &
FRONTEND_PID=$!

# Dọn dẹp tiến trình khi nhận tín hiệu dừng
cleanup() {
    echo -e "\n\033[0;33m[INFO] Đang dừng toàn bộ dịch vụ (Backend PID: $BACKEND_PID, Frontend PID: $FRONTEND_PID)...\033[0m"
    kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
    if command -v lsof >/dev/null 2>&1; then
        lsof -ti:8000 | xargs kill -9 2>/dev/null || true
        lsof -ti:5173 | xargs kill -9 2>/dev/null || true
    elif command -v fuser >/dev/null 2>&1; then
        fuser -k 8000/tcp 2>/dev/null || true
        fuser -k 5173/tcp 2>/dev/null || true
    fi
    echo -e "\033[0;32m[OK] Đã dọn dẹp sạch sẽ các tiến trình. Tạm biệt!\033[0m"
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

echo ""
echo "=========================================================="
echo -e "\033[0;32m  HỆ THỐNG ĐÃ KHỞI CHẠY THÀNH CÔNG!\033[0m"
echo -e "  - Frontend:         \033[1;33mhttp://localhost:5173\033[0m"
echo -e "  - Backend API:      \033[1;33mhttp://127.0.0.1:8000\033[0m"
echo -e "  - Backend Docs:     \033[1;33mhttp://127.0.0.1:8000/docs\033[0m"
echo -e "  Nhấn \033[1;36m[Ctrl + C]\033[0m để dừng toàn bộ hệ thống."
echo "=========================================================="
echo ""

# Chờ tiến trình
wait

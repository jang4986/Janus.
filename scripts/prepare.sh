
#!/usr/bin/env bash

set -Eeuo pipefail

# ======================================================
# PATH
# ======================================================

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"

cd "$ROOT_DIR"

# ======================================================
# 1. VALIDATE ENVIRONMENT
# ======================================================

echo "========== 1. VALIDATE E2E ENVIRONMENT =========="

if [[ "${APP_ENV:-}" != "e2e" ]]; then
    echo "ERROR: APP_ENV must be e2e."
    exit 1
fi

: "${DATABASE_URL:?Missing DATABASE_URL}"
: "${E2E_USER_EMAIL:?Missing E2E_USER_EMAIL}"
: "${E2E_USER_PASSWORD:?Missing E2E_USER_PASSWORD}"
: "${E2E_MODERATOR_EMAIL:?Missing E2E_MODERATOR_EMAIL}"
: "${E2E_MODERATOR_PASSWORD:?Missing E2E_MODERATOR_PASSWORD}"

: "${E2E_VIDEO_01_URL:?Missing E2E_VIDEO_01_URL}"
: "${E2E_VIDEO_02_URL:?Missing E2E_VIDEO_02_URL}"

: "${E2E_VIDEO_01_TITLE:?Missing E2E_VIDEO_01_TITLE}"
: "${E2E_VIDEO_02_TITLE:?Missing E2E_VIDEO_02_TITLE}"

: "${UPLOAD_DIR:?Missing UPLOAD_DIR}"
: "${E2E_VIDEO_DIR:?Missing E2E_VIDEO_DIR}"

if [[ "${E2E_ALLOW_DATABASE_RESET:-NO}" != "YES" ]]; then
    echo "ERROR: E2E_ALLOW_DATABASE_RESET must be YES."
    exit 1
fi

if [[ ! -d "$BACKEND_DIR" ]]; then
    echo "ERROR: Backend directory not found: $BACKEND_DIR"
    exit 1
fi

command -v uv >/dev/null 2>&1 || {
    echo "ERROR: uv is not installed."
    exit 1
}

echo "Environment validation passed."

# ======================================================
# 2. DOWNLOAD VIDEO FIXTURES
# ======================================================

echo
echo "========== 2. DOWNLOAD VIDEO FIXTURES =========="

bash "$ROOT_DIR/scripts/download_videos.sh"

# ======================================================
# 3. BACKEND OPERATIONS
# ======================================================

echo
echo "========== 3. BACKEND OPERATIONS =========="

cd "$BACKEND_DIR"

# Cho phép Python import module app từ backend
# và import script từ root.
export PYTHONPATH="$BACKEND_DIR:$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}"

echo "Backend directory: $BACKEND_DIR"

# ------------------------------------------------------
# 3.1. ALEMBIC MIGRATION
# ------------------------------------------------------

echo
echo "========== 3.1. RUN ALEMBIC MIGRATION =========="

uv run alembic upgrade head

# ------------------------------------------------------
# 3.2. RESET DATABASE
# ------------------------------------------------------

echo
echo "========== 3.2. RESET E2E DATABASE =========="

uv run python "$ROOT_DIR/scripts/reset_database.py"

# ------------------------------------------------------
# 3.3. SEED DATABASE
# ------------------------------------------------------

echo
echo "========== 3.3. SEED E2E DATABASE =========="

uv run python "$ROOT_DIR/scripts/seed_database.py"

# ======================================================
# 4. COMPLETED
# ======================================================

echo
echo "=============================================="
echo "       E2E PREPARATION COMPLETED"
echo "=============================================="
echo
echo "Database : E2E"
echo "User     : $E2E_USER_EMAIL"
echo "Moderator: $E2E_MODERATOR_EMAIL"
echo "Videos   : 2"
echo
echo "Ready to run Playwright."

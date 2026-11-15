# ==============================================================================
# PBL6 AI SHORT VIDEO MODERATION - 1-CLICK DEV STARTUP SCRIPT (WINDOWS POWERSHELL)
# ==============================================================================
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Set-Location $PSScriptRoot

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  PBL6 AI SHORT VIDEO MODERATION - 1-CLICK DEV RUNNER    " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# Ham don dep tien trinh dang chiem cong
function Stop-PortProcess {
    param([int]$Port)
    try {
        $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        foreach ($conn in $connections) {
            $procId = $conn.OwningProcess
            if ($procId -and $procId -ne $PID) {
                Write-Host "[CLEANUP] Dang dung tien trinh PID $procId dang chiem cong $Port..." -ForegroundColor Yellow
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            }
        }
    } catch {}
}

# Don dep cong 8000 va 5173 truoc khi khoi chay neu co tien trinh treo cu
Stop-PortProcess 8000
Stop-PortProcess 5173

# Buoc 1: Kiem tra cong cu he thong (uv, node, npm)
Write-Host "`n[1/5] Kiem tra cong cu he thong (uv, node, npm)..." -ForegroundColor Cyan
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] 'uv' chua duoc cai dat! Vui long cai dat: https://docs.astral.sh/uv/" -ForegroundColor Red
    exit 1
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] 'node' chua duoc cai dat! Vui long cai dat Node.js." -ForegroundColor Red
    exit 1
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] 'npm' chua duoc cai dat! Vui long cai dat npm." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Moi truong uv, node, npm da san sang!" -ForegroundColor Green

# Buoc 2: Dong bo thu vien Backend (uv sync)
Write-Host "`n[2/5] Dong bo thu vien Backend (uv sync)..." -ForegroundColor Cyan
uv sync --directory backend
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] uv sync that bai! Vui long kiem tra ket noi mang hoac pyproject.toml." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Thu vien Backend da duoc dong bo hoan tat!" -ForegroundColor Green

# Buoc 3: Kiem tra dependencies Frontend
Write-Host "`n[3/5] Kiem tra dependencies Frontend..." -ForegroundColor Cyan
if (-not (Test-Path "$PSScriptRoot\frontend\node_modules")) {
    Write-Host "[*] Chua tim thay frontend/node_modules. Dang chay 'npm --prefix frontend install'..." -ForegroundColor Yellow
    npm --prefix frontend install
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Cai dat dependencies frontend that bai!" -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] Cai dat dependencies frontend hoan tat!" -ForegroundColor Green
} else {
    Write-Host "[OK] frontend/node_modules da san sang!" -ForegroundColor Green
}

# Buoc 4: Dong bo Database len ban moi nhat (Alembic migration)
Write-Host "`n[4/5] Dong bo Database len ban moi nhat (Alembic migration)..." -ForegroundColor Cyan
uv run --directory backend alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Dong bo Database that bai! Ma loi: $LASTEXITCODE. Huy khoi chay server." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Database da duoc dong bo len ban moi nhat!" -ForegroundColor Green

# Buoc 5: Khoi dong song song Backend va Frontend
Write-Host "`n[5/5] Khoi dong song song Backend va Frontend..." -ForegroundColor Cyan

# Khoi chay Backend (Uvicorn)
$backendProc = Start-Process -FilePath "uv" -ArgumentList "run", "--directory", "backend", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000" -PassThru -NoNewWindow

# Khoi chay Frontend (Vite)
$frontendProc = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "npm run --prefix frontend dev" -PassThru -NoNewWindow

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "  HE THONG DA KHOI CHAY THANH CONG!                      " -ForegroundColor Green
Write-Host "  - Frontend:         http://localhost:5173               " -ForegroundColor Yellow
Write-Host "  - Backend API:      http://127.0.0.1:8000               " -ForegroundColor Yellow
Write-Host "  - Backend Docs:     http://127.0.0.1:8000/docs          " -ForegroundColor Yellow
Write-Host "  Nhan [Ctrl + C] de dung toan bo he thong.              " -ForegroundColor Cyan
Write-Host "==========================================================`n" -ForegroundColor Green

# Lang nghe va Clean Shutdown khi thoat
try {
    while ($true) {
        Start-Sleep -Milliseconds 500
        if ($backendProc.HasExited) {
            Write-Host "[CANH BAO] Tien trinh Backend da dung (ExitCode: $($backendProc.ExitCode))." -ForegroundColor Red
            break
        }
        if ($frontendProc.HasExited) {
            Write-Host "[CANH BAO] Tien trinh Frontend da dung (ExitCode: $($frontendProc.ExitCode))." -ForegroundColor Red
            break
        }
    }
}
finally {
    Write-Host "`n[STOPPING] Dang dung toan bo dich vu va giai phong cong..." -ForegroundColor Yellow
    if ($backendProc -and -not $backendProc.HasExited) {
        taskkill /PID $backendProc.Id /T /F >$null 2>&1
    }
    if ($frontendProc -and -not $frontendProc.HasExited) {
        taskkill /PID $frontendProc.Id /T /F >$null 2>&1
    }
    Stop-PortProcess 8000
    Stop-PortProcess 5173
    Write-Host "[OK] Da don dep sach se toan bo dich vu. Tam biet!" -ForegroundColor Green
}


#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

VIDEO_01_URL="${E2E_VIDEO_01_URL:?Missing E2E_VIDEO_01_URL}"
VIDEO_02_URL="${E2E_VIDEO_02_URL:?Missing E2E_VIDEO_02_URL}"

VIDEO_DIR="${E2E_VIDEO_DIR:-storage/e2e}"

if [[ "$VIDEO_DIR" = /* ]]; then
    OUTPUT_DIR="$VIDEO_DIR"
else
    OUTPUT_DIR="$ROOT_DIR/$VIDEO_DIR"
fi

mkdir -p "$OUTPUT_DIR"

command -v curl >/dev/null 2>&1 || {
    echo "ERROR: curl is required"
    exit 1
}

download_video() {
    local url="$1"
    local filename="$2"
    local output="$OUTPUT_DIR/$filename"
    local temp="$output.part"

    if [[ -s "$output" && "${FORCE_DOWNLOAD:-0}" != "1" ]]; then
        echo "Using existing fixture: $filename"
        return
    fi

    echo "Downloading $filename..."

    rm -f "$temp"

    if ! curl \
        --fail \
        --location \
        --silent \
        --show-error \
        --retry 3 \
        --retry-delay 2 \
        --max-time 300 \
        "$url" \
        -o "$temp"; then

        rm -f "$temp"
        echo "ERROR: Failed to download $filename"
        return 1
    fi

    if [[ ! -s "$temp" ]]; then
        rm -f "$temp"
        echo "ERROR: Empty video file: $filename"
        return 1
    fi

    # Kiểm tra codec nếu ffprobe đã được cài đặt.
    if command -v ffprobe >/dev/null 2>&1; then
        if ! ffprobe -v error \
            -select_streams v:0 \
            -show_entries stream=codec_name \
            -of csv=p=0 "$temp" >/dev/null; then

            rm -f "$temp"
            echo "ERROR: Invalid video: $filename"
            return 1
        fi
    fi

    mv "$temp" "$output"

    echo "Downloaded successfully: $filename"
}

download_video "$VIDEO_01_URL" "e2e-video-01.mp4"
download_video "$VIDEO_02_URL" "e2e-video-02.mp4"

echo "All video fixtures are ready."

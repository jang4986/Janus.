/** Định dạng dùng chung: dung lượng, thời gian, trạng thái video. */

export function formatViewCount(num) {
  const n = Number(num) || 0
  if (n >= 1_000_000) {
    const formatted = (n / 1_000_000).toFixed(1).replace(/\.0$/, '')
    return `${formatted}M`
  }
  if (n >= 1_000) {
    const formatted = (n / 1_000).toFixed(1).replace(/\.0$/, '')
    return `${formatted}K`
  }
  return n.toLocaleString('vi-VN')
}

export function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 MB'
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function formatDateTime(iso) {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

export const VIDEO_STATUS_LABEL = {
  processing: 'Đang xử lý',
  pending_review: 'Chờ duyệt',
  published: 'Đã phát',
  rejected: 'Bị từ chối',
  failed: 'Lỗi',
  deleted: 'Đã xóa',
}

export function statusTone(status) {
  if (status === 'published') return 'ok'
  if (status === 'pending_review' || status === 'processing') return 'warn'
  if (status === 'rejected' || status === 'failed') return 'danger'
  return 'neutral'
}

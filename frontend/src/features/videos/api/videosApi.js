import { apiFetch, apiUrl } from '@/shared/api/client'

export function fetchFeed({ limit = 8, cursor } = {}) {
  const query = new URLSearchParams({ limit: String(limit) })
  if (cursor) query.set('cursor', cursor)
  return apiFetch(`/v1/feed?${query}`, { auth: false })
}

export function fetchMyVideos() {
  return apiFetch('/v1/videos')
}

export function fetchAiResult(videoId) {
  return apiFetch(`/v1/videos/${videoId}/ai`)
}

export function streamUrl(videoId) {
  return apiUrl(`/v1/videos/${videoId}/stream`)
}

export function thumbnailUrl(videoId) {
  return apiUrl(`/v1/videos/${videoId}/thumbnail`)
}

export function deleteVideo(videoId) {
  return apiFetch(`/v1/videos/${videoId}`, { method: 'DELETE' })
}

export function updateVideo(videoId, payload) {
  return apiFetch(`/v1/videos/${videoId}`, { method: 'PATCH', body: payload })
}

export function searchVideosByTag(tag, { limit = 12, cursor } = {}) {
  const query = new URLSearchParams({ tag, limit: String(limit) })
  if (cursor) query.set('cursor', cursor)
  return apiFetch(`/v1/videos/search?${query}`, { auth: false })
}

export function searchVideosByDescription(description, { limit = 12, cursor } = {}) {
  const query = new URLSearchParams({ description, limit: String(limit) })
  if (cursor) query.set('cursor', cursor)
  return apiFetch(`/v1/videos/search?${query}`, { auth: false })
}

export function reportVideo(videoId, reason) {
  return apiFetch(`/v1/videos/${videoId}/reports`, { method: 'POST', body: { reason } })
}

export function uploadVideo({ file, caption, onProgress, signal }) {
  const form = new FormData()
  form.append('file', file)
  const query = new URLSearchParams()
  if (caption) query.set('caption', caption)
  const path = `/v1/videos${query.size ? `?${query}` : ''}`

  // Fetch does not expose upload progress; keep a compatible API for the upload hook.
  onProgress?.(0)
  return apiFetch(path, { method: 'POST', body: form, signal }).then((video) => {
    onProgress?.(100)
    return video
  })
}

export function recordVideoView(videoId) {
  return apiFetch(`/v1/videos/${videoId}/views`, { method: 'POST', auth: false })
}

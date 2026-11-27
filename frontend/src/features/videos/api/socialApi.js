import { apiFetch } from '@/shared/api/client'

export function toggleLike(videoId) {
  return apiFetch(`/v1/videos/${videoId}/like`, { method: 'POST', auth: true })
}

export function listComments(videoId, { page = 1, pageSize = 20 } = {}) {
  const query = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  return apiFetch(`/v1/videos/${videoId}/comments?${query}`, { auth: false })
}

export function createComment(videoId, content) {
  return apiFetch(`/v1/videos/${videoId}/comments`, { method: 'POST', body: { content } })
}

export function deleteComment(commentId) {
  return apiFetch(`/v1/comments/${commentId}`, { method: 'DELETE' })
}

export function toggleBookmark(videoId) {
  return apiFetch(`/v1/videos/${videoId}/bookmark`, { method: 'POST' })
}

export function toggleFollow(userId) {
  return apiFetch(`/v1/users/${userId}/follow`, { method: 'POST' })
}

export function fetchBookmarks({ page = 1, pageSize = 20 } = {}) {
  const query = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  return apiFetch(`/v1/users/me/bookmarks?${query}`)
}

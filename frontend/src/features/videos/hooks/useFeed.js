import { useCallback, useEffect, useRef, useState } from 'react'

import { fetchFeed } from '../api/videosApi'

/**
 * Hook quản lý nạp feed video:
 * - First load: Nạp trước 3 video (limit=3).
 * - Phân trang cursor: Khi gần tới cuối feed (activeIndex >= videos.length - 2), nạp tiếp 2 video (limit=2).
 * - Dừng khi backend hết video (has_more=false hoặc không còn cursor); không xáo trộn lặp lại.
 */
export function useFeed(activeIndex = 0) {
  const [videos, setVideos] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState('')

  // Bộ đệm lưu trữ danh sách các video duy nhất đã nạp từ backend
  const poolRef = useRef([])
  const hasMoreRef = useRef(true)
  const nextCursorRef = useRef(null)
  const pageSequenceRef = useRef(0)
  const refreshSequenceRef = useRef(0)
  const isFetchingRef = useRef(false)

  // Khởi tạo hoặc tải lại feed từ đầu
  const refresh = useCallback(async () => {
    const requestSequence = ++refreshSequenceRef.current
    setError('')
    setLoading(true)
    isFetchingRef.current = true
    try {
      const res = await fetchFeed({ limit: 3 })
      if (requestSequence !== refreshSequenceRef.current) return
      const items = res?.items || (Array.isArray(res) ? res : [])
      pageSequenceRef.current = 0
      poolRef.current = [...items]
      hasMoreRef.current = Boolean(res?.has_more && res?.next_cursor)
      nextCursorRef.current = res?.next_cursor || null

      const initialVideos = items.map((item) => ({ ...item }))
      setVideos(initialVideos)
    } catch (requestError) {
      if (requestSequence !== refreshSequenceRef.current) return
      setError(requestError.detail || requestError.message || 'Không thể tải feed video.')
      setVideos([])
      poolRef.current = []
    } finally {
      if (requestSequence === refreshSequenceRef.current) {
        setLoading(false)
        isFetchingRef.current = false
      }
    }
  }, [])

  // Nạp thêm video qua cursor pagination từ backend; dừng khi backend hết video
  const loadMore = useCallback(async () => {
    if (isFetchingRef.current) return
    if (!hasMoreRef.current || !nextCursorRef.current) return

    const requestSequence = refreshSequenceRef.current
    isFetchingRef.current = true
    setLoadingMore(true)
    try {
      const res = await fetchFeed({ limit: 2, cursor: nextCursorRef.current })
      if (requestSequence !== refreshSequenceRef.current) return
      const newItems = res?.items || []
      hasMoreRef.current = Boolean(res?.has_more && res?.next_cursor)
      nextCursorRef.current = res?.next_cursor || null

      if (newItems.length > 0) {
        const knownIds = new Set(poolRef.current.map((item) => item.id))
        const freshItems = newItems.filter((item) => !knownIds.has(item.id))
        freshItems.forEach((item) => poolRef.current.push(item))

        if (freshItems.length > 0) {
          const pageSequence = pageSequenceRef.current++
          const mapped = freshItems.map((item) => ({ ...item }))
          setVideos((prev) => [...prev, ...mapped])
        }
      }
    } catch {
      if (requestSequence === refreshSequenceRef.current) hasMoreRef.current = false
    } finally {
      if (requestSequence === refreshSequenceRef.current) {
        isFetchingRef.current = false
        setLoadingMore(false)
      }
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  // Tự động kích hoạt loadMore khi người dùng cuộn gần tới cuối danh sách (còn 1-2 video)
  useEffect(() => {
    if (loading || videos.length === 0) return
    if (activeIndex >= videos.length - 2) {
      loadMore()
    }
  }, [activeIndex, videos.length, loading, loadMore])

  return {
    videos,
    loading,
    loadingMore,
    error,
    refresh,
    loadMore,
  }
}

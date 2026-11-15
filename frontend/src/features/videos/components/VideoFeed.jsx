import { useEffect, useMemo, useRef, useState } from 'react'

import { EmptyState, ErrorNote, Spinner } from '@/shared/components/Feedback'
import { useFeed } from '../hooks/useFeed'
import VideoSlide from './VideoSlide'

/**
 * Feed cuộn dọc toàn màn hình kiểu TikTok (Snap-scrolling).
 * Mỗi slide giữ video element để có thể phát thủ công; chỉ slide đang xem được tải trước.
 */
export default function VideoFeed({ focusVideo = null }) {
  const [activeIndex, setActiveIndex] = useState(0)
  const { videos, loading, error, refresh } = useFeed(activeIndex)
  const containerRef = useRef(null)
  const displayVideos = useMemo(() => {
    if (!focusVideo) return videos
    return [focusVideo, ...videos.filter((video) => video.id !== focusVideo.id)]
  }, [focusVideo, videos])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    const slides = Array.from(container.querySelectorAll('.slide'))
    if (slides.length === 0) return

    const observer = new IntersectionObserver(
      (entries) => {
        const mostVisible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0]
        if (!mostVisible || mostVisible.intersectionRatio < 0.5) return
        const index = slides.indexOf(mostVisible.target)
        if (index >= 0) setActiveIndex(index)
      },
      { root: container, threshold: [0.5, 0.75] },
    )

    slides.forEach((slide) => observer.observe(slide))

    // Chọn slide gần tâm vùng xem nhất để tránh lệch activeIndex khi kích thước
    // viewport thay đổi hoặc trình duyệt phát nhiều sự kiện quan sát cùng lúc.
    const handleScroll = () => {
      const center = container.getBoundingClientRect().top + container.clientHeight / 2
      let nearestIndex = 0
      let nearestDistance = Infinity
      slides.forEach((slide, index) => {
        const rect = slide.getBoundingClientRect()
        const distance = Math.abs(rect.top + rect.height / 2 - center)
        if (distance < nearestDistance) {
          nearestDistance = distance
          nearestIndex = index
        }
      })
      setActiveIndex(nearestIndex)
    }

    container.addEventListener('scroll', handleScroll, { passive: true })
    handleScroll()

    return () => {
      observer.disconnect()
      container.removeEventListener('scroll', handleScroll)
    }
  }, [displayVideos])

  useEffect(() => {
    if (!focusVideo || displayVideos.length === 0) return undefined
    const focusedIndex = displayVideos.findIndex((video) => video.id === focusVideo.id)
    const container = containerRef.current
    const slide = container?.querySelectorAll('.slide')[focusedIndex]
    if (!container || !slide || focusedIndex < 0) return undefined

    setActiveIndex(focusedIndex)
    const frame = window.requestAnimationFrame(() => {
      const containerTop = container.getBoundingClientRect().top
      const slideTop = slide.getBoundingClientRect().top
      container.scrollTop = container.scrollTop + slideTop - containerTop
    })
    return () => window.cancelAnimationFrame(frame)
  }, [displayVideos, focusVideo])

  if (loading && displayVideos.length === 0) {
    return (
      <div className="feed-center">
        <Spinner label="Đang tải feed" />
      </div>
    )
  }

  if (error && displayVideos.length === 0) {
    return (
      <div className="feed-center">
        <ErrorNote>{error}</ErrorNote>
        <button type="button" className="button ghost" onClick={refresh}>
          Thử lại
        </button>
      </div>
    )
  }

  if (!Array.isArray(displayVideos) || displayVideos.length === 0) {
    return (
      <div className="feed-center">
        <EmptyState
          icon="film"
          title="Chưa có video nào được phát"
          hint="Hãy tải video đầu tiên lên Janus để xem kết quả kiểm duyệt tại đây."
          action={
            <a className="button primary" href="/upload">
              Tải video lên
            </a>
          }
        />
      </div>
    )
  }

  return (
    <div className="feed-wrapper">
      <div className="feed" ref={containerRef}>
        {displayVideos.map((video, index) => (
          <VideoSlide
            key={video.id}
            video={video}
            index={index}
            activeIndex={activeIndex}
            isActive={index === activeIndex}
            onReported={refresh}
          />
        ))}
      </div>
    </div>
  )
}

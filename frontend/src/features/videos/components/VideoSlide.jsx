import { useCallback, useEffect, useRef, useState } from 'react'

import Icon from '@/shared/components/Icon'
import { recordVideoView } from '../api/videosApi'
import ReportDialog from './ReportDialog'
import CommentDrawer from './CommentDrawer'
import { toggleLike, toggleFollow, toggleBookmark } from '../api/socialApi'
import { streamUrl, thumbnailUrl } from '../api/videosApi'
import { useAuth } from '@/features/auth/AuthContext'

function formatTime(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

function formatViewCount(num) {
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

/**
 * Một video slide trong feed dọc.
 * Áp dụng cơ chế Cửa sổ trượt (Sliding Window):
 * - Chỉ mount thẻ <video> cho slide hiện tại và kế tiếp; slide kế tiếp không tải trước dữ liệu.
 * - Tất cả các video còn lại chỉ mount ảnh thumbnail <img src={thumbnail_url}> để tiết kiệm băng thông.
 */
export default function VideoSlide({
  video,
  index,
  activeIndex,
  isActive: propIsActive,
  onReported,
}) {
  const containerRef = useRef(null)
  const videoRef = useRef(null)
  const volumeRef = useRef(null)
  const shouldPlayRef = useRef(false)
  const [playing, setPlaying] = useState(false)
  const [mediaError, setMediaError] = useState('')
  const fallbackStream = streamUrl(video.id)
  const [source, setSource] = useState(video.stream_url || fallbackStream)
  const [muted, setMuted] = useState(true)
  const [volume, setVolume] = useState(0.5)
  const [reporting, setReporting] = useState(false)
  const [showComments, setShowComments] = useState(false)
  const [liked, setLiked] = useState(false)
  const [followed, setFollowed] = useState(false)
  const [bookmarked, setBookmarked] = useState(false)
  const [showVolume, setShowVolume] = useState(false)
  const [fullscreen, setFullscreen] = useState(false)
  const [captionExpanded, setCaptionExpanded] = useState(false)
  const [duration, setDuration] = useState(0)
  const [currentTime, setCurrentTime] = useState(0)
  const [seeking, setSeeking] = useState(false)
  const [currentViews, setCurrentViews] = useState(
    Number(video.view_count ?? video.views ?? video.play_count ?? 0)
  )
  const hasCountedRef = useRef(false)
  const { isAuthenticated } = useAuth()

  const isActive =
    propIsActive !== undefined
      ? propIsActive
      : index !== undefined && activeIndex !== undefined
      ? index === activeIndex
      : false

  useEffect(() => {
    setSource(video.stream_url || fallbackStream)
    setMediaError('')
    setPlaying(false)
    setLiked(false)
    setFollowed(false)
    setBookmarked(false)
    setMuted(true)
    setVolume(0.5)
    setShowVolume(false)
    setShowComments(false)
    setFullscreen(false)
    setCurrentViews(Number(video.view_count ?? video.views ?? video.play_count ?? 0))
    hasCountedRef.current = false
    if (videoRef.current) {
      videoRef.current.muted = true
      videoRef.current.volume = 0.5
    }
  }, [video.id, video.stream_url, video.view_count, video.views, fallbackStream])

  useEffect(() => {
    if (!isActive) {
      hasCountedRef.current = false
    }
  }, [isActive])

  // Tự động phát khi slide trở thành active và dừng khi lướt sang video khác
  useEffect(() => {
    const element = videoRef.current
    if (!element) return

    if (isActive) {
      shouldPlayRef.current = true
      element
        .play()
        .then(() => setPlaying(true))
        .catch(() => {
          // Trình duyệt chặn autoplay có tiếng -> chuyển muted rồi phát lại
          if (!element.muted) {
            element.muted = true
            setMuted(true)
            element.play().then(() => setPlaying(true)).catch(() => setPlaying(false))
          } else {
            setPlaying(false)
          }
        })
    } else {
      shouldPlayRef.current = false
      element.pause()
      element.currentTime = 0
      setCurrentTime(0)
      setPlaying(false)
    }
  }, [isActive])

  useEffect(() => {
    function onChange() {
      setFullscreen(Boolean(document.fullscreenElement))
    }
    document.addEventListener('fullscreenchange', onChange)
    return () => document.removeEventListener('fullscreenchange', onChange)
  }, [])

  async function togglePlayback() {
    const element = videoRef.current
    if (!element) return
    if (mediaError) {
      setMediaError('')
      element.load()
    }
    if (element.paused) {
      try {
        shouldPlayRef.current = true
        await element.play()
        setPlaying(true)
      } catch {
        setPlaying(false)
      }
    } else {
      shouldPlayRef.current = false
      element.pause()
      setPlaying(false)
    }
  }

  function handleMediaError() {
    if (source !== fallbackStream) {
      setSource(fallbackStream)
      setMediaError('')
      return
    }
    setPlaying(false)
    setMediaError('Không tải được video. Hãy bấm vào video để thử lại.')
  }

  function handleCanPlay() {
    if (!isActive || !shouldPlayRef.current || !videoRef.current) return
    videoRef.current.play().then(() => setPlaying(true)).catch(() => setPlaying(false))
  }

  async function handleLike() {
    if (!isAuthenticated) return
    const previous = liked
    setLiked(!previous)
    try {
      const result = await toggleLike(video.id)
      setLiked(Boolean(result.is_liked))
    } catch {
      setLiked(previous)
    }
  }

  async function handleFollow() {
    if (!isAuthenticated || !video.owner_id) return
    const previous = followed
    setFollowed(!previous)
    try {
      const result = await toggleFollow(video.owner_id)
      setFollowed(Boolean(result.is_following))
    } catch {
      setFollowed(previous)
    }
  }

  async function handleBookmark() {
    if (!isAuthenticated) return
    const previous = bookmarked
    setBookmarked(!previous)
    try {
      const result = await toggleBookmark(video.id)
      setBookmarked(Boolean(result.is_bookmarked))
    } catch {
      setBookmarked(previous)
    }
  }

  function toggleMute() {
    const element = videoRef.current
    if (!element) return
    const nextMuted = !(muted || volume === 0)
    if (nextMuted) {
      setMuted(true)
      element.muted = true
    } else {
      setMuted(false)
      element.muted = false
      if (volume === 0) {
        setVolume(0.5)
        element.volume = 0.5
      }
    }
  }

  function changeVolume(e) {
    const value = Number(e.target.value)
    setVolume(value)
    const element = videoRef.current
    if (!element) return
    element.volume = value
    if (value === 0) {
      setMuted(true)
      element.muted = true
    } else {
      setMuted(false)
      element.muted = false
    }
  }

  function toggleFullscreen() {
    const videoEl = videoRef.current
    const containerEl = containerRef.current
    if (!videoEl) return
    const el = fullscreen ? containerEl : videoEl
    if (!el) return
    if (document.fullscreenElement) {
      document.exitFullscreen()
      setFullscreen(false)
      return
    }
    el.requestFullscreen?.().then(() => setFullscreen(true)).catch(() => {})
  }

  const triggerCountView = useCallback(async () => {
    if (hasCountedRef.current) return
    hasCountedRef.current = true

    try {
      const res = await recordVideoView(video.id)
      if (res && typeof res.view_count === 'number') {
        setCurrentViews(res.view_count)
      } else if (res?.counted) {
        setCurrentViews((prev) => prev + 1)
      }
    } catch (err) {
      console.debug('Failed to record video view:', err)
    }
  }, [video.id])

  function handleTimeUpdate() {
    const el = videoRef.current
    if (!el || !isActive) return
    setCurrentTime(el.currentTime)
    if (hasCountedRef.current) return
    // Điều kiện 1: Đã xem liên tục từ 5 giây trở lên
    if (el.currentTime >= 5) {
      triggerCountView()
    } else if (
      el.duration &&
      el.duration < 5 &&
      el.currentTime >= Math.max(0, el.duration - 0.25)
    ) {
      // Hỗ trợ video ngắn dưới 5s khi phát lặp lại (loop)
      triggerCountView()
    }
  }

  function handleEnded() {
    const el = videoRef.current
    if (!el || !isActive || hasCountedRef.current) return
    // Điều kiện 2: Video có thời lượng ngắn (< 5s) và phát hết video
    if (el.duration && el.duration < 5) {
      triggerCountView()
    }
  }

  const likeCount = video.likes || video.like_count || 0

  function handleSeekStart(e) {
    const el = videoRef.current
    if (!el) return
    setSeeking(true)
    const rect = e.currentTarget.getBoundingClientRect()
    const x = (e.touches ? e.touches[0].clientX : e.clientX) - rect.left
    const time = (x / rect.width) * el.duration
    el.currentTime = time
    setCurrentTime(time)
  }

  function handleSeekMove(e) {
    const el = videoRef.current
    if (!el || !seeking) return
    const rect = e.currentTarget.getBoundingClientRect()
    const x = (e.touches ? e.touches[0].clientX : e.clientX) - rect.left
    const time = (x / rect.width) * el.duration
    el.currentTime = time
    setCurrentTime(time)
  }

  function handleSeekEnd() {
    setSeeking(false)
  }

  return (
    <article className="slide" ref={containerRef}>
      <div className="slide-stage">
        <div className="slide-video-frame">
          <div className="video-progress-wrapper" onClick={togglePlayback}>
            <div className="video-progress-time">
              <span>{formatTime(currentTime)}</span>
              <span>{formatTime(duration)}</span>
            </div>
            <div
              className="video-progress-track"
              onMouseDown={handleSeekStart}
              onMouseMove={handleSeekMove}
              onMouseUp={handleSeekEnd}
              onMouseLeave={handleSeekEnd}
              onTouchStart={(e) => handleSeekStart(e.nativeEvent)}
              onTouchMove={(e) => handleSeekMove(e.nativeEvent)}
              onTouchEnd={handleSeekEnd}
            >
              <div
                className={`video-progress-bar ${seeking ? 'seeking' : ''}`}
                style={{
                  width: duration
                    ? `${Math.min(100, (currentTime / duration) * 100)}%`
                    : '0%',
                }}
              />
            </div>
          </div>
          <video
            ref={videoRef}
            src={source}
            poster={thumbnailUrl(video.id)}
            loop
            playsInline
            autoPlay={isActive}
            muted={muted}
            preload={isActive ? 'auto' : 'none'}
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
            onTimeUpdate={handleTimeUpdate}
            onEnded={handleEnded}
            onError={handleMediaError}
            onCanPlay={handleCanPlay}
            onDurationChange={(e) => setDuration(e.target.duration)}
            onLoadedMetadata={(e) => setDuration(e.target.duration)}
          />
        </div>
        {!playing && (
          <button type="button" className="slide-play" onClick={togglePlayback} aria-label="Phát video">
            <Icon name="play" size={26} />
          </button>
        )}
        {mediaError && <button type="button" className="slide-media-error" onClick={togglePlayback} aria-label="Thử tải video lại">{mediaError}</button>}
      </div>

      <div className="slide-meta">
        <div className="slide-user-row">
          <span className="slide-user">@{video.owner_name || 'janus'}</span>
          <button
            type="button"
            className={`slide-follow ${followed ? 'active' : ''}`}
            onClick={handleFollow}
            disabled={!isAuthenticated || !video.owner_id}
          >
            {followed ? 'Đang theo dõi' : 'Theo dõi'}
          </button>
        </div>
        <div className="slide-view">
          <Icon name="play" size={12} />
          <span>{formatViewCount(currentViews)} lượt xem</span>
        </div>
        <p className="slide-caption">{video.caption || 'Không có mô tả'}</p>
      </div>

      <div className="slide-actions">
        <button
          type="button"
          className={`rail-button ${liked ? 'active' : ''}`}
          onClick={handleLike}
          aria-label="Thích"
        >
          <Icon name={liked ? 'heart-filled' : 'heart'} size={22} />
          <span>{(likeCount + (liked ? 1 : 0)).toLocaleString('vi-VN')}</span>
        </button>
        <button
          type="button"
          className={`rail-button ${bookmarked ? 'active' : ''}`}
          onClick={handleBookmark}
          aria-label={bookmarked ? 'Bỏ lưu video' : 'Lưu video'}
          disabled={!isAuthenticated}
        >
          <Icon name="bookmark" size={21} />
          <span>{bookmarked ? 'Đã lưu' : 'Lưu'}</span>
        </button>
        <button
          type="button"
          className="rail-button"
          aria-label="Bình luận"
          onClick={() => setShowComments(true)}
        >
          <Icon name="message" size={22} />
          <span>Bình luận</span>
        </button>
        <div
          className="rail-volume"
          ref={volumeRef}
          onMouseEnter={() => setShowVolume(true)}
          onMouseLeave={() => {
            window.setTimeout(() => {
              const wrapper = volumeRef.current
              if (!wrapper) return
              if (!wrapper.matches(':hover')) {
                setShowVolume(false)
              }
            }, 120)
          }}
        >
          <button
            type="button"
            className="rail-button"
            onClick={toggleMute}
            aria-label={muted || volume === 0 ? 'Bật tiếng' : 'Tắt tiếng'}
          >
            <Icon name={muted || volume === 0 ? 'mute' : 'volume'} size={22} />
            <span>{muted || volume === 0 ? 'Bật tiếng' : 'Âm lượng'}</span>
          </button>
          <div
            className={`volume-slider ${showVolume ? 'visible' : ''}`}
            onMouseEnter={() => setShowVolume(true)}
            onMouseLeave={() => {
              window.setTimeout(() => {
                const wrapper = volumeRef.current
                if (!wrapper) return
                if (!wrapper.matches(':hover')) {
                  setShowVolume(false)
                }
              }, 120)
            }}
          >
            <input
              type="range"
              min="0"
              max="1"
              step="0.01"
              value={muted ? 0 : volume}
              onChange={changeVolume}
            />
          </div>
        </div>
        <button
          type="button"
          className="rail-button"
          onClick={toggleFullscreen}
          aria-label={fullscreen ? 'Thu nhỏ' : 'Phóng to'}
        >
          <Icon name="expand" size={22} />
          <span>{fullscreen ? 'Thu nhỏ' : 'Phóng to'}</span>
        </button>
        <button
          type="button"
          className="rail-button"
          onClick={() => setReporting(true)}
          aria-label="Báo cáo"
        >
          <Icon name="flag" size={22} />
          <span>Báo cáo</span>
        </button>
      </div>

      {reporting && (
        <ReportDialog
          video={video}
          onClose={() => setReporting(false)}
          onReported={onReported}
        />
      )}
      {showComments && (
        <CommentDrawer video={video} onClose={() => setShowComments(false)} />
      )}
    </article>
  )
}

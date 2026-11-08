import { useCallback, useEffect, useState } from 'react'

import { useNavigate } from 'react-router-dom'

import Icon from '@/shared/components/Icon'
import { EmptyState, ErrorNote, Spinner } from '@/shared/components/Feedback'
import { fetchBookmarks, toggleBookmark } from '@/features/videos/api/socialApi'
import { thumbnailUrl } from '@/features/videos/api/videosApi'
import { formatDateTime } from '@/shared/lib/format'
import '@/styles/bookmarks.css'

export default function BookmarksPage() {
  const navigate = useNavigate()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const result = await fetchBookmarks()
      setItems(result.items || [])
    } catch (requestError) {
      setError(requestError.detail || requestError.message || 'Không tải được video đã lưu.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  async function remove(videoId, event) {
    if (event) {
      event.stopPropagation()
    }
    try {
      await toggleBookmark(videoId)
      setItems((current) => current.filter((video) => video.id !== videoId))
    } catch (requestError) {
      setError(requestError.detail || requestError.message || 'Không thể bỏ lưu video.')
    }
  }

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <p className="page-sub">Những video bạn muốn xem lại sau.</p>
        </div>
        <button className="button ghost" onClick={refresh} disabled={loading}>Làm mới</button>
      </div>
      <ErrorNote>{error}</ErrorNote>
      {loading ? (
        <Spinner label="Đang tải video đã lưu" />
      ) : items.length === 0 ? (
        <EmptyState icon="film" title="Chưa có video đã lưu" hint="Lưu video từ feed để tìm lại tại đây." />
      ) : (
        <div className="bookmark-grid">
          {items.map((video) => {
            const title = video.caption || 'Không có mô tả'
            const authorName = video.author?.username || video.owner_name || video.username || 'janus'
            const views = Number(video.view_count || 0)
            return (
              <article className="bookmark-card" key={video.id}>
                <div className="bookmark-card-media">
                  <img src={thumbnailUrl(video.id)} alt="" loading="lazy" />
                  <button type="button" className="bookmark-play" onClick={(event) => navigateToVideo(video.id, event)}>
                    <Icon name="play" size={16} />
                  </button>
                  {views > 0 && (
                    <span className="bookmark-duration">{views.toLocaleString('vi-VN')} lượt xem</span>
                  )}
                </div>
                <button type="button" className="bookmark-link" onClick={(event) => navigateToVideo(video.id, event)}>
                  <span className="bookmark-card-copy">
                    <p className="bookmark-card-title" title={title}>{title}</p>
                    <div className="bookmark-card-details">
                      <span className="bookmark-card-user">@{authorName}</span>
                      {video.like_count !== undefined && <span className="bookmark-card-likes"><Icon name="heart" size={12} />{video.like_count}</span>}
                    </div>
                  </span>
                </button>
                <button type="button" className="bookmark-remove" onClick={(event) => remove(video.id, event)} title="Bỏ lưu">
                  <Icon name="trash" size={16} />
                </button>
              </article>
            )
          })}
        </div>
      )}
    </div>
  )

  function navigateToVideo(videoId, event) {
    event.stopPropagation()
    navigate(`/?video_id=${encodeURIComponent(videoId)}`)
  }
}

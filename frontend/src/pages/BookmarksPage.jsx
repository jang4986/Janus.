import { useCallback, useEffect, useState } from 'react'

import Icon from '@/shared/components/Icon'
import { EmptyState, ErrorNote, Spinner } from '@/shared/components/Feedback'
import { fetchBookmarks, toggleBookmark } from '@/features/videos/api/socialApi'
import { streamUrl, thumbnailUrl } from '@/features/videos/api/videosApi'
import { formatDateTime } from '@/shared/lib/format'
import '@/styles/bookmarks.css'

export default function BookmarksPage() {
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

  async function remove(videoId) {
    try {
      await toggleBookmark(videoId)
      setItems((current) => current.filter((video) => video.id !== videoId))
    } catch (requestError) {
      setError(requestError.detail || requestError.message || 'Không thể bỏ lưu video.')
    }
  }

  return <div className="page"><div className="page-head"><div><span className="overline">BỘ SƯU TẬP CỦA BẠN</span><h1>Video đã lưu</h1><p className="page-sub">Những video bạn muốn xem lại sau.</p></div><button className="button ghost" onClick={refresh} disabled={loading}>Làm mới</button></div><ErrorNote>{error}</ErrorNote>{loading?<Spinner label="Đang tải video đã lưu"/>:items.length===0?<EmptyState icon="film" title="Chưa có video đã lưu" hint="Lưu video từ feed để tìm lại tại đây."/>:<div className="bookmark-grid">{items.map(video=><article className="bookmark-card" key={video.id}><div className="bookmark-card-media"><video src={streamUrl(video.id)} poster={thumbnailUrl(video.id)} controls playsInline preload="none"/></div><div className="bookmark-card-copy"><div className="bookmark-card-title"><strong>{video.caption||video.original_filename||'Video chưa đặt tên'}</strong>{video.caption&&video.original_filename&&<span className="bookmark-filename">{video.original_filename}</span>}</div><div className="bookmark-card-details"><span>{video.owner_name||'Janus'}</span><span>{formatDateTime(video.created_at)}</span>{video.view_count!=null&&<span>{Number(video.view_count).toLocaleString('vi-VN')} lượt xem</span>}</div></div><button className="bookmark-remove" onClick={()=>remove(video.id)} aria-label="Bỏ lưu video"><Icon name="bookmark" size={17}/></button></article>)}</div>}</div>
}

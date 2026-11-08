import { useEffect, useState } from 'react'
import { useSearchParams, Link } from 'react-router-dom'

import { fetchMyVideos } from '@/features/videos/api/videosApi'
import VideoFeed from '@/features/videos/components/VideoFeed'
import FeedGrid from '@/features/videos/components/FeedGrid'
import Icon from '@/shared/components/Icon'

export default function FeedPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const description = searchParams.get('description')?.trim()
  const [focusedVideo, setFocusedVideo] = useState(null)
  const [myVideosLoaded, setMyVideosLoaded] = useState(false)
  const view = searchParams.get('view') === 'grid' ? 'grid' : 'video'

  const videoId = searchParams.get('video_id')

  useEffect(() => {
    if (!videoId || focusedVideo || myVideosLoaded) return
    fetchMyVideos()
      .then((items) => {
        const found = items.find((video) => video.id === videoId)
        if (found) {
          setFocusedVideo(found)
          const nextParams = new URLSearchParams(searchParams)
          nextParams.set('view', 'video')
          setSearchParams(nextParams, { replace: true })
        }
      })
      .finally(() => setMyVideosLoaded(true))
  }, [searchParams, videoId, focusedVideo, myVideosLoaded])

  function setView(nextView) {
    const nextParams = new URLSearchParams(searchParams)
    if (nextView === 'video') nextParams.delete('view')
    else nextParams.set('view', nextView)
    setSearchParams(nextParams, { replace: true })
  }

  function selectGridVideo(video) {
    setFocusedVideo(video)
    setView('video')
  }

  if (description) {
    return (
      <div className="feed-page">
        <div className="feed-page-header">
          <div className="feed-tabs">
            <span className="feed-tab active">Kết quả: {description}</span>
          </div>
          {focusedVideo ? (
            <button type="button" className="button ghost small" onClick={() => setFocusedVideo(null)}>
              <Icon name="arrow" size={14} style={{ transform: 'rotate(180deg)' }} />
              <span>Quay lại lưới</span>
            </button>
          ) : (
            <Link to="/" className="button ghost small" aria-label="Quay lại feed chính">
              <Icon name="arrow" size={14} style={{ transform: 'rotate(180deg)' }} />
              <span>Xem feed cuộn</span>
            </Link>
          )}
        </div>
        {focusedVideo
          ? <VideoFeed focusVideo={focusedVideo} />
          : <FeedGrid activeDescription={description} onSelectVideo={selectGridVideo} />}
      </div>
    )
  }

  return (
    <div className="feed-page">
      {view === 'video'
        ? <VideoFeed focusVideo={focusedVideo} />
        : <FeedGrid onSelectVideo={selectGridVideo} />}
    </div>
  )
}

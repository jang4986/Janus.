import { useState } from 'react'
import { useSearchParams, useNavigate, useLocation } from 'react-router-dom'

import VideoFeed from '@/features/videos/components/VideoFeed'
import FeedGrid from '@/features/videos/components/FeedGrid'

export default function FeedPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const location = useLocation()
  const description = searchParams.get('description')?.trim()
  const view = searchParams.get('view') === 'grid' ? 'grid' : 'video'
  const focusVideo = location.state?.focusVideo || null

  function onSelectVideo(video) {
    navigate(`/?video_id=${encodeURIComponent(video.id)}`, {
      state: { focusVideo: video },
    })
  }

  if (description) {
    return (
      <div className="feed-page">
        <div className="feed-page-header">
          <span className="feed-tab active">Kết quả: {description}</span>
        </div>
        <FeedGrid activeDescription={description} onSelectVideo={onSelectVideo} />
      </div>
    )
  }

  return (
    <div className="feed-page">
      {view === 'video'
        ? <VideoFeed focusVideo={focusVideo} />
        : <FeedGrid onSelectVideo={onSelectVideo} />}
    </div>
  )
}

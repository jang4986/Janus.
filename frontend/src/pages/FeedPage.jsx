import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import VideoFeed from '@/features/videos/components/VideoFeed'
import FeedGrid from '@/features/videos/components/FeedGrid'

export default function FeedPage() {
  const [searchParams] = useSearchParams()
  const description = searchParams.get('description')?.trim()
  const view = searchParams.get('view') === 'grid' ? 'grid' : 'video'

  if (description) {
    return (
      <div className="feed-page">
        <div className="feed-page-header">
          <span className="feed-tab active">Kết quả: {description}</span>
        </div>
        <FeedGrid activeDescription={description} />
      </div>
    )
  }

  return (
    <div className="feed-page">
      {view === 'video'
        ? <VideoFeed />
        : <FeedGrid />}
    </div>
  )
}

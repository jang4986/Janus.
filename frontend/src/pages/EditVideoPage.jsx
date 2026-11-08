import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import Icon from '@/shared/components/Icon'
import { ErrorNote, Spinner } from '@/shared/components/Feedback'
import { fetchMyVideos, streamUrl, thumbnailUrl, updateVideo } from '@/features/videos/api/videosApi'
import { toggleFollow } from '@/features/videos/api/socialApi'
import { useAuth } from '@/features/auth/AuthContext'
import { formatViewCount } from '@/shared/lib/format'
import '@/styles/profile-editor.css'

export default function EditVideoPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [videos, setVideos] = useState([])
  const [selectedVideo, setSelectedVideo] = useState(null)
  const [title, setTitle] = useState('')
  const [visibility, setVisibility] = useState('public')
  const [allowComments, setAllowComments] = useState(true)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [followed, setFollowed] = useState(false)
  const { isAuthenticated } = useAuth()

  useEffect(() => {
    fetchMyVideos()
      .then((items) => {
        setVideos(items)
        const requestedId = searchParams.get('video_id')
        const selected = items.find((video) => video.id === requestedId)
        if (selected) {
          setSelectedVideo(selected)
          setTitle(selected.caption || selected.original_filename || '')
          setVisibility(selected.visibility || 'public')
          setAllowComments(selected.allow_comments !== false)
          setFollowed(Boolean(selected.is_followed))
        } else {
          setError('Không tìm thấy video.')
        }
      })
      .catch((requestError) => setError(requestError.detail || requestError.message))
      .finally(() => setLoading(false))
  }, [searchParams])

  async function submit(e) {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      await updateVideo(selectedVideo.id, { caption: title, visibility, allow_comments: allowComments })
      navigate('/profile')
    } catch (requestError) {
      setError(requestError.detail || requestError.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleFollow() {
    if (!isAuthenticated || !selectedVideo?.owner_id) return
    const previous = followed
    setFollowed(!previous)
    try {
      const result = await toggleFollow(selectedVideo.owner_id)
      setFollowed(Boolean(result.is_following))
    } catch {
      setFollowed(previous)
    }
  }

  if (loading) {
    return (
      <div className="page">
        <div className="page-head">
          <div>
            <h1>Chỉnh sửa thông tin video</h1>
          </div>
        </div>
        <div style={{ padding: '40px 0', textAlign: 'center' }}>
          <Spinner label="Đang tải video" />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="page">
        <div className="page-head">
          <div>
            <h1>Chỉnh sửa thông tin video</h1>
          </div>
        </div>
        <div style={{ padding: '40px 0', textAlign: 'center' }}>
          <ErrorNote>{error}</ErrorNote>
        </div>
      </div>
    )
  }

  const isRejected = selectedVideo?.status === 'rejected'
  const isPending = selectedVideo?.status === 'pending_review' || selectedVideo?.status === 'pending'
  const isPublished = selectedVideo?.status === 'published'

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Chỉnh sửa thông tin video</h1>
        </div>
      </div>

      <form className="edit-video-grid" onSubmit={submit}>
        <section className="card edit-card">
          <header className="card-head">
            <div>
              <h2>Thông tin cơ bản</h2>
              <p className="card-sub">Điền thông tin hiển thị trên video</p>
            </div>
          </header>
          <div className="card-body form-stack">
            <label className="field">
              <span>
                Mô tả video <em>không bắt buộc</em>
              </span>
              <textarea
                className="text-input"
                value={title}
                maxLength={500}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Video này nói về điều gì?"
                style={{ height: '100px', resize: 'none', overflowY: 'auto' }}
              />
            </label>
            <label className="field">
              <span>Chế độ hiển thị</span>
              <select className="text-input" value={visibility} onChange={(e) => setVisibility(e.target.value)}>
                <option value="public">Công khai</option>
                <option value="private">Riêng tư</option>
              </select>
            </label>
            <label className="field">
              <span>
                <input type="checkbox" checked={allowComments} onChange={(e) => setAllowComments(e.target.checked)} /> Cho phép bình luận
              </span>
            </label>
          </div>
        </section>

        {isRejected && (
          <div className="status-banner status-banner--rejected">
            <Icon name="shield" size={16} />
            <span>Video đã bị từ chối do vi phạm tiêu chuẩn cộng đồng</span>
          </div>
        )}

        {isPending && (
          <div className="status-banner status-banner--pending">
            <Icon name="clock" size={16} />
            <span>Video đang được lưu trữ và chờ kiểm duyệt viên xem xét thủ công</span>
          </div>
        )}

        <aside className="card preview-card">
          <div className="preview-thumb">
            <video
              src={streamUrl(selectedVideo.id)}
              poster={thumbnailUrl(selectedVideo.id)}
              muted
              playsInline
              preload="metadata"
            />
          </div>
          <div className="preview-meta">
            <div className="preview-user-row">
              <span className="preview-user">@{selectedVideo.owner_name || 'janus'}</span>
              <button
                type="button"
                className={`preview-follow ${followed ? 'active' : ''}`}
                onClick={handleFollow}
                disabled={!isAuthenticated || !selectedVideo.owner_id}
              >
                {followed ? 'Đang theo dõi' : 'Theo dõi'}
              </button>
            </div>
            <div className="preview-view">
              <Icon name="play" size={12} />
              <span>{formatViewCount(selectedVideo.view_count ?? selectedVideo.views ?? selectedVideo.play_count ?? 0)} lượt xem</span>
            </div>
            <p className={`preview-caption ${expanded ? '' : 'truncate-2'}`}>
              {selectedVideo.caption || 'Không có mô tả'}
            </p>
            {selectedVideo.caption && selectedVideo.caption.length > 80 && !expanded && (
              <button type="button" className="preview-expand" onClick={() => setExpanded(true)}>
                (...)
              </button>
            )}
          </div>
        </aside>

        <div className="edit-actions">
          <button type="button" className="button ghost" onClick={() => navigate(-1)}>
            Hủy
          </button>
          {isPublished && (
            <Link to="/" className="button ghost">
              Xem ở feed <Icon name="arrow" size={14} />
            </Link>
          )}
          <button type="submit" className="button primary" disabled={saving}>
            {saving ? 'Đang lưu...' : 'Lưu thay đổi'}
          </button>
        </div>
      </form>
    </div>
  )
}

import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import Icon from '@/shared/components/Icon'
import { StatusBadge } from '@/shared/components/Feedback'
import { VIDEO_STATUS_LABEL } from '@/shared/lib/format'
import { fetchMyVideos, thumbnailUrl, updateVideo } from '@/features/videos/api/videosApi'

const STATUS_TABS = [
  { id: 'all', label: 'Tất cả' },
  { id: 'published', label: 'Đã phát' },
  { id: 'pending', label: 'Chờ duyệt' },
  { id: 'rejected', label: 'Bị từ chối' },
]

export default function EditVideoPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [step, setStep] = useState('list')
  const [activeTab, setActiveTab] = useState('all')
  const [videos, setVideos] = useState([])
  const [selectedVideo, setSelectedVideo] = useState(null)
  const [title, setTitle] = useState('')
  const [visibility, setVisibility] = useState('public')
  const [allowComments, setAllowComments] = useState(true)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    fetchMyVideos()
      .then((items) => {
        setVideos(items)
        const requestedId = searchParams.get('video_id')
        const selected = items.find((video) => video.id === requestedId)
        if (selected) selectVideo(selected)
      })
      .catch((requestError) => setError(requestError.detail || requestError.message))
      .finally(() => setLoading(false))
  }, [searchParams])

  function selectVideo(video) {
    setSelectedVideo(video)
    setTitle(video.caption || video.original_filename || '')
    setVisibility(video.visibility || 'public')
    setAllowComments(video.allow_comments !== false)
    setStep('edit')
  }

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

  // Đếm số lượng video theo từng trạng thái
  const counts = {
    all: videos.length,
    published: videos.filter((v) => v.status === 'published').length,
    pending: videos.filter((v) => v.status === 'pending' || v.status === 'pending_review' || v.status === 'processing').length,
    rejected: videos.filter((v) => v.status === 'rejected' || v.status === 'failed').length,
  }

  // Lọc danh sách video theo tab đang chọn
  const filteredVideos = videos.filter((v) => {
    if (activeTab === 'published') return v.status === 'published'
    if (activeTab === 'pending') return v.status === 'pending' || v.status === 'pending_review' || v.status === 'processing'
    if (activeTab === 'rejected') return v.status === 'rejected' || v.status === 'failed'
    return true
  })

  if (step === 'list') {
    return (
      <div className="page">
        <div className="page-head">
          <div>
            <h1>Video của tôi</h1>
            <p className="page-sub">Chọn video bạn đã tải lên để chỉnh sửa thông tin.</p>
          </div>
        </div>
        {error && <p className="error-note">{error}</p>}

        <section className="card">
          <header className="card-head">
            <div>
              <h2>Danh sách video</h2>
              <p className="card-sub">Chọn một video để cập nhật</p>
            </div>
          </header>
          <div className="card-body">
            {/* Cụm Tabs lọc trạng thái */}
            <div className="card-tabs">
              <div className="tabs" role="tablist">
                {STATUS_TABS.map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    role="tab"
                    aria-selected={activeTab === tab.id}
                    className={activeTab === tab.id ? 'tab active' : 'tab'}
                    onClick={() => setActiveTab(tab.id)}
                  >
                    {tab.label} ({counts[tab.id] ?? 0})
                  </button>
                ))}
              </div>
            </div>

            {loading ? (
              <p>Đang tải danh sách video...</p>
            ) : filteredVideos.length === 0 ? (
              <p className="ai-empty">Không có video nào trong mục này.</p>
            ) : (
              <div className="video-list">
                {filteredVideos.map((video) => (
                  <button key={video.id} type="button" className="video-list-item" onClick={() => selectVideo(video)}>
                    <div className="video-list-thumb">
                      <img src={thumbnailUrl(video.id)} alt="" />
                      <Icon name="play" size={18} />
                    </div>
                    <div className="video-list-info">
                      <strong>{video.caption || video.original_filename || 'Video không tiêu đề'}</strong>
                      <span>Chỉnh sửa thông tin</span>
                    </div>
                    <div className="video-list-status">
                      <StatusBadge status={video.status} label={VIDEO_STATUS_LABEL[video.status] || video.status} />
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </section>
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
          <p className="page-sub">Cập nhật caption và quyền hiển thị cho "{selectedVideo?.caption || selectedVideo?.original_filename}".</p>
        </div>
      </div>
      {error && <p className="error-note">{error}</p>}

      <form className="edit-video-grid" onSubmit={submit}>
        <section className="card">
          <header className="card-head">
            <div>
              <h2>Thông tin cơ bản</h2>
              <p className="card-sub">Điền thông tin hiển thị trên video</p>
            </div>
          </header>
          <div className="card-body form-stack">
            <label className="field">
              <span>Caption</span>
              <input className="text-input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Nhập tiêu đề video" />
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

        <div className="edit-actions" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {isRejected && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px 14px',
                borderRadius: '8px',
                background: 'rgba(255, 92, 92, 0.12)',
                border: '1px solid rgba(255, 92, 92, 0.3)',
                color: 'var(--danger)',
                fontSize: '13px',
                fontWeight: 500,
              }}
            >
              <Icon name="shield" size={16} />
              <span>Video đã bị từ chối do vi phạm tiêu chuẩn cộng đồng</span>
            </div>
          )}

          {isPending && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px 14px',
                borderRadius: '8px',
                background: 'rgba(255, 176, 32, 0.12)',
                border: '1px solid rgba(255, 176, 32, 0.3)',
                color: 'var(--warn)',
                fontSize: '13px',
                fontWeight: 500,
              }}
            >
              <Icon name="clock" size={16} />
              <span>Video đang được lưu trữ và chờ kiểm duyệt viên xem xét thủ công</span>
            </div>
          )}

          <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', flexWrap: 'wrap' }}>
            <button type="button" className="button ghost" onClick={() => setStep('list')}>Quay lại danh sách</button>
            <button type="button" className="button ghost" onClick={() => navigate(-1)}>Hủy</button>
            {isPublished && (
              <Link to="/" className="button ghost">
                Xem ở feed <Icon name="arrow" size={14} />
              </Link>
            )}
            <button type="submit" className="button primary" disabled={saving}>{saving ? 'Đang lưu...' : 'Lưu thay đổi'}</button>
          </div>
        </div>
      </form>
    </div>
  )
}

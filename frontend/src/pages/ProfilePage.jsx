import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import Icon from '@/shared/components/Icon'
import { EmptyState, ErrorNote, Spinner, StatusBadge } from '@/shared/components/Feedback'
import { VIDEO_STATUS_LABEL, formatBytes, formatDateTime } from '@/shared/lib/format'
import { useAuth } from '@/features/auth/AuthContext'
import AiResultPanel from '@/features/videos/components/AiResultPanel'
import { deleteVideo, fetchMyVideos, streamUrl, thumbnailUrl } from '@/features/videos/api/videosApi'
import { fetchMyModerationStats } from '@/features/moderation/api/moderationApi'
import '@/styles/profile.css'
import '@/styles/profile-editor.css'

const STATUS_TABS = [
  { id: 'all', label: 'Tất cả' },
  { id: 'published', label: 'Đã phát' },
  { id: 'pending', label: 'Chờ duyệt' },
  { id: 'rejected', label: 'Bị từ chối' },
]

export default function ProfilePage() {
  const { user, updateProfile } = useAuth()
  const navigate = useNavigate()
  const [videos, setVideos] = useState([])
  const [activeTab, setActiveTab] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedId, setSelectedId] = useState(null)
  const [busyId, setBusyId] = useState(null)
  const [moderationStats, setModerationStats] = useState(null)
  const [moderationStatsError, setModerationStatsError] = useState('')
  const [profileDraft, setProfileDraft] = useState({ display_name: user.display_name, bio: user.bio || '', avatar_url: user.avatar_url || '' })
  const [profileSaving, setProfileSaving] = useState(false)
  const [profileMessage, setProfileMessage] = useState('')

  async function saveProfile(event) {
    event.preventDefault()
    setProfileSaving(true)
    setProfileMessage('')
    try {
      await updateProfile({ ...profileDraft, avatar_url: profileDraft.avatar_url.trim() || null })
      setProfileMessage('Thông tin cá nhân đã được cập nhật.')
    } catch (requestError) {
      setProfileMessage(requestError.detail || requestError.message || 'Chưa thể cập nhật hồ sơ.')
    } finally {
      setProfileSaving(false)
    }
  }

  useEffect(() => {
    if (user.role !== 'moderator') return
    fetchMyModerationStats()
      .then(setModerationStats)
      .catch((requestError) => setModerationStatsError(requestError.detail || requestError.message))
  }, [user.role])

  const load = useCallback(async () => {
    setError('')
    try {
      const items = await fetchMyVideos()
      setVideos(items)
      setSelectedId((current) => (current && items.some((item) => item.id === current) ? current : items[0]?.id ?? null))
    } catch (requestError) {
      setError(requestError.detail || requestError.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function remove(video) {
    setBusyId(video.id)
    try {
      await deleteVideo(video.id)
      await load()
    } catch (requestError) {
      setError(requestError.detail || requestError.message)
    } finally {
      setBusyId(null)
    }
  }

  // Số lượng đếm cho từng tab
  const counts = {
    all: videos.length,
    published: videos.filter((item) => item.status === 'published').length,
    pending: videos.filter((item) => item.status === 'pending' || item.status === 'pending_review' || item.status === 'processing').length,
    rejected: videos.filter((item) => item.status === 'rejected' || item.status === 'failed').length,
  }

  // Lọc theo tab đang chọn
  const filteredVideos = videos.filter((item) => {
    if (activeTab === 'published') return item.status === 'published'
    if (activeTab === 'pending') return item.status === 'pending' || item.status === 'pending_review' || item.status === 'processing'
    if (activeTab === 'rejected') return item.status === 'rejected' || item.status === 'failed'
    return true
  })

  function handleTabChange(tabId) {
    setActiveTab(tabId)
    const matched = videos.filter((item) => {
      if (tabId === 'published') return item.status === 'published'
      if (tabId === 'pending') return item.status === 'pending' || item.status === 'pending_review' || item.status === 'processing'
      if (tabId === 'rejected') return item.status === 'rejected' || item.status === 'failed'
      return true
    })
    if (matched.length > 0 && !matched.some((m) => m.id === selectedId)) {
      setSelectedId(matched[0].id)
    }
  }

  if (loading) {
    return (
      <div className="page-center">
        <Spinner label="Đang tải danh sách video" />
      </div>
    )
  }

  return (
    <div className="page">
      <div className="profile-head">
        <span className="avatar avatar-lg">{user.avatar_url ? <img src={user.avatar_url} alt="" /> : user.display_name.slice(0, 2).toUpperCase()}</span>
        <div>
          <h1>{user.display_name}</h1>
          <p className="page-sub">
            {user.email} · vai trò <strong>{user.role === 'moderator' ? 'Kiểm duyệt viên' : user.role === 'admin' ? 'Quản trị viên' : 'Người dùng'}</strong>
          </p>
        </div>
        <div className="stat-row">
          <button
            type="button"
            className={`stat stat-button ${activeTab === 'all' ? 'active' : ''}`}
            onClick={() => handleTabChange('all')}
          >
            <strong>{counts.all}</strong>
            <span>Tất cả</span>
          </button>
          <button
            type="button"
            className={`stat stat-button ${activeTab === 'published' ? 'active' : ''}`}
            onClick={() => handleTabChange('published')}
          >
            <strong>{counts.published}</strong>
            <span>Đã phát</span>
          </button>
          <button
            type="button"
            className={`stat stat-button ${activeTab === 'pending' ? 'active' : ''}`}
            onClick={() => handleTabChange('pending')}
          >
            <strong>{counts.pending}</strong>
            <span>Chờ duyệt</span>
          </button>
          <button
            type="button"
            className={`stat stat-button ${activeTab === 'rejected' ? 'active' : ''}`}
            onClick={() => handleTabChange('rejected')}
          >
            <strong>{counts.rejected}</strong>
            <span>Bị từ chối</span>
          </button>
        </div>
      </div>

      <form className="profile-edit-panel" onSubmit={saveProfile}>
        <div className="profile-edit-heading">
          <div><span className="overline">HỒ SƠ CỦA BẠN</span><h2>Thông tin cá nhân</h2></div>
          {profileDraft.avatar_url && <img className="profile-avatar-preview" src={profileDraft.avatar_url} alt="Ảnh đại diện xem trước" />}
        </div>
        <div className="profile-edit-fields">
          <label className="field"><span>Tên hiển thị</span><input className="text-input" value={profileDraft.display_name} maxLength={120} required onChange={(event) => setProfileDraft((draft) => ({ ...draft, display_name: event.target.value }))} /></label>
          <label className="field"><span>Liên kết ảnh đại diện</span><input className="text-input" type="url" placeholder="https://…" value={profileDraft.avatar_url} onChange={(event) => setProfileDraft((draft) => ({ ...draft, avatar_url: event.target.value }))} /></label>
          <label className="field profile-bio-field"><span>Giới thiệu</span><textarea className="text-input" rows={3} maxLength={500} value={profileDraft.bio} onChange={(event) => setProfileDraft((draft) => ({ ...draft, bio: event.target.value }))} placeholder="Một vài dòng về bạn" /></label>
        </div>
        <div className="profile-edit-footer"><span aria-live="polite">{profileMessage}</span><button className="button primary" type="submit" disabled={profileSaving}>{profileSaving ? 'Đang lưu…' : 'Lưu hồ sơ'}</button></div>
      </form>

      <ErrorNote>{error}</ErrorNote>

      {user.role === 'moderator' && <section className="moderator-profile-stats" aria-label="Thống kê kiểm duyệt">
        <div className="moderator-profile-heading"><div><span className="overline">KHÔNG GIAN MODERATOR</span><h2>Hoạt động kiểm duyệt</h2></div><span className="moderator-role-chip">Moderator</span></div>
        {moderationStatsError && <ErrorNote>{moderationStatsError}</ErrorNote>}
        <div className="moderator-stat-grid">
          <article><span>Quyết định đã xử lý</span><strong>{moderationStats?.decisions_count ?? '—'}</strong></article>
            <article><span>Video bị từ chối</span><strong>{moderationStats?.rejected_videos_count ?? '—'}</strong></article>
          <article><span>Báo cáo đang chờ</span><strong>{moderationStats?.open_reports_count ?? '—'}</strong></article>
          <article><span>Khiếu nại đã xử lý</span><strong>{moderationStats?.handled_appeals_count ?? '—'}</strong></article>
        </div>
      </section>}

      {videos.length === 0 ? (
        <EmptyState
          icon="upload"
          title="Bạn chưa tải video nào"
          hint="Video tải lên sẽ hiển thị tại đây cùng kết quả phân tích AI."
          action={
            <a className="button primary" href="/upload">
              Tải video đầu tiên
            </a>
          }
        />
      ) : (
        <>
          {/* Thanh Tabs lọc trạng thái */}
          <div className="card-tabs" style={{ marginBottom: '16px' }}>
            <div className="tabs" role="tablist">
              {STATUS_TABS.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  aria-selected={activeTab === tab.id}
                  className={activeTab === tab.id ? 'tab active' : 'tab'}
                  onClick={() => handleTabChange(tab.id)}
                >
                  {tab.label} ({counts[tab.id] ?? 0})
                </button>
              ))}
            </div>
          </div>

          <div className="profile-grid">
            {filteredVideos.length === 0 ? (
              <p className="ai-empty">Không có video nào trong danh mục này.</p>
            ) : (
              <ul className="video-list">
                {filteredVideos.map((video) => (
                  <li key={video.id} className={video.id === selectedId ? 'video-row active' : 'video-row'}>
                    <button type="button" className="video-row-main" onClick={() => setSelectedId(video.id)}>
                      <span className="video-row-thumb">
                        <video src={streamUrl(video.id)} poster={thumbnailUrl(video.id)} muted playsInline preload="none" />
                      </span>
                      <span className="video-row-copy">
                        <strong>{video.caption || video.original_filename}</strong>
                        <span>
                          {formatDateTime(video.created_at)} · {formatBytes(video.size_bytes)}
                        </span>
                      </span>
                      <StatusBadge status={video.status} label={VIDEO_STATUS_LABEL[video.status] || video.status} />
                    </button>
                    <span className="video-row-actions">
                      <button type="button" className="button ghost small" onClick={() => navigate(`/edit-video?video_id=${encodeURIComponent(video.id)}`)}>
                        <Icon name="edit" size={14} /> Chỉnh sửa
                      </button>
                      <button type="button" className="icon-button danger" onClick={() => remove(video)} disabled={busyId === video.id} aria-label="Xóa video" title="Xóa video">
                        <Icon name="trash" size={16} />
                      </button>
                    </span>
                  </li>
                ))}
              </ul>
            )}

            {selectedId && <AiResultPanel videoId={selectedId} />}
          </div>
        </>
      )}
    </div>
  )
}

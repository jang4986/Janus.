import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import Icon from '@/shared/components/Icon'
import { EmptyState, ErrorNote, Modal, Spinner, StatusBadge } from '@/shared/components/Feedback'
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
  const { user, updateProfile, updateAvatar } = useAuth()
  const navigate = useNavigate()
  const [videos, setVideos] = useState([])
  const [activeTab, setActiveTab] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedId, setSelectedId] = useState(null)
  const [busyId, setBusyId] = useState(null)
  const [moderationStats, setModerationStats] = useState(null)
  const [moderationStatsError, setModerationStatsError] = useState('')
  const [confirmDeleteId, setConfirmDeleteId] = useState(null)
  const [editOpen, setEditOpen] = useState(false)
  const [avatarOpen, setAvatarOpen] = useState(false)
  const [avatarFile, setAvatarFile] = useState(null)
  const [avatarPreview, setAvatarPreview] = useState(null)
  const [avatarSaving, setAvatarSaving] = useState(false)
  const [profileDraft, setProfileDraft] = useState({
    display_name: user?.display_name ?? '',
    bio: user?.bio ?? '',
    avatar_url: user?.avatar_url ?? '',
  })
  const [profileSaving, setProfileSaving] = useState(false)
  const [profileMessage, setProfileMessage] = useState('')
  const avatarInputRef = useRef(null)

  async function saveProfile(event) {
    event.preventDefault()
    setProfileSaving(true)
    setProfileMessage('')
    try {
      await updateProfile({ ...profileDraft, avatar_url: profileDraft.avatar_url.trim() || null })
      setProfileMessage('Thông tin cá nhân đã được cập nhật.')
      setEditOpen(false)
    } catch (requestError) {
      setProfileMessage(requestError.detail || requestError.message || 'Chưa thể cập nhật hồ sơ.')
    } finally {
      setProfileSaving(false)
    }
  }

  async function saveAvatar(event) {
    event.preventDefault()
    if (!avatarFile) return
    setAvatarSaving(true)
    try {
      await updateAvatar(avatarFile)
      setAvatarOpen(false)
      setAvatarFile(null)
      setAvatarPreview(null)
    } catch (requestError) {
      setProfileMessage(requestError.detail || requestError.message || 'Không thể cập nhật ảnh đại diện.')
    } finally {
      setAvatarSaving(false)
    }
  }

  function handleAvatarFileChange(event) {
    const file = event.target.files?.[0]
    if (!file) return
    setAvatarFile(file)
    setAvatarPreview(URL.createObjectURL(file))
  }

  function openEdit() {
    setProfileDraft({
      display_name: user?.display_name ?? '',
      bio: user?.bio ?? '',
      avatar_url: user?.avatar_url ?? '',
    })
    setProfileMessage('')
    setEditOpen(true)
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
        <div className="profile-avatar-wrap">
          <span className="avatar avatar-lg">
            {user.avatar_url ? <img src={user.avatar_url} alt="" /> : user.display_name.slice(0, 2).toUpperCase()}
          </span>
          <button
            type="button"
            className="avatar-edit"
            title="Chỉnh sửa ảnh đại diện"
            onClick={() => setAvatarOpen(true)}
            aria-label="Chỉnh sửa ảnh đại diện"
          >
            <Icon name="edit" size={14} />
          </button>
          <input
            ref={avatarInputRef}
            type="file"
            accept="image/*"
            hidden
            onChange={handleAvatarFileChange}
          />
        </div>
        <div>
          <h1>
            {user.display_name} <span className="profile-id">#{user.discriminator ?? ''}</span>
          </h1>
          <p className="page-sub">{user.email}</p>
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

      <section className="profile-intro">
        <div className="profile-edit-heading">
          <div>
            <h2>Giới thiệu</h2>
          </div>
        </div>
        <div className="profile-intro-body">
          <p className={user.bio ? '' : 'empty'}>{user.bio || 'Chưa có giới thiệu.'}</p>
        </div>
        <div className="profile-intro-actions">
          <button className="button ghost" type="button" onClick={openEdit}>
            Chỉnh sửa thông tin cá nhân
          </button>
        </div>
      </section>

      {editOpen && (
        <Modal title="Chỉnh sửa thông tin cá nhân" onClose={() => setEditOpen(false)}>
          <form onSubmit={saveProfile}>
            <div className="profile-edit-fields">
              <label className="field">
                <span>Tên hiển thị</span>
                <input
                  className="text-input"
                  value={profileDraft.display_name}
                  maxLength={120}
                  required
                  onChange={(event) => setProfileDraft((draft) => ({ ...draft, display_name: event.target.value }))}
                />
              </label>
              <label className="field profile-bio-field">
                <span>Giới thiệu</span>
                <textarea
                  className="text-input"
                  rows={3}
                  maxLength={500}
                  value={profileDraft.bio}
                  onChange={(event) => setProfileDraft((draft) => ({ ...draft, bio: event.target.value }))}
                  placeholder="Một vài dòng về bạn"
                />
              </label>
            </div>
            <div className="profile-edit-footer">
              <span aria-live="polite">{profileMessage}</span>
              <button className="button primary" type="submit" disabled={profileSaving}>
                {profileSaving ? 'Đang lưu…' : 'Lưu hồ sơ'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {avatarOpen && (
        <Modal title="Thay đổi ảnh đại diện" onClose={() => setAvatarOpen(false)}>
          <form onSubmit={saveAvatar}>
            <div className="avatar-modal">
              <div className="avatar-current">
                <span className="avatar-label">{avatarPreview ? 'Ảnh đại diện mới' : 'Ảnh đại diện hiện tại'}</span>
                <div className="avatar-current-image">
                  {avatarPreview ? (
                    <>
                      <img src={avatarPreview} alt="Xem trước" />
                      <button
                        type="button"
                        className="button ghost avatar-remove"
                        onClick={() => {
                          setAvatarFile(null)
                          setAvatarPreview(null)
                        }}
                        aria-label="Xóa ảnh đã chọn"
                      >
                        <Icon name="trash" size={14} />
                      </button>
                    </>
                  ) : user.avatar_url ? (
                    <img src={user.avatar_url} alt="Avatar hiện tại" />
                  ) : (
                    <span className="avatar-placeholder">{user.display_name.slice(0, 2).toUpperCase()}</span>
                  )}
                </div>
              </div>

              <label className="field avatar-file-field">
                <span>Chọn ảnh mới</span>
                <input
                  type="file"
                  accept="image/*"
                  ref={avatarInputRef}
                  onChange={handleAvatarFileChange}
                  required
                />
                <span className="field-hint">JPEG, PNG, tối đa 5 MB</span>
              </label>

              <div className="avatar-actions">
                {avatarFile && (
                  <button
                    type="button"
                    className="button ghost"
                    onClick={() => {
                      setAvatarFile(null)
                      setAvatarPreview(null)
                    }}
                  >
                    Chọn lại
                  </button>
                )}
                <button className="button primary" type="submit" disabled={avatarSaving || !avatarFile}>
                  {avatarSaving ? 'Đang lưu…' : 'Lưu ảnh đại diện'}
                </button>
              </div>
            </div>
          </form>
        </Modal>
      )}

      {confirmDeleteId && (
        <Modal title="Xác nhận xóa video" onClose={() => setConfirmDeleteId(null)}>
          <p>Bạn có chắc chắn muốn xóa video này? Hành động này không thể hoàn tác.</p>
          <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', marginTop: '12px' }}>
            <button type="button" className="button ghost" onClick={() => setConfirmDeleteId(null)}>
              Hủy
            </button>
            <button
              type="button"
              className="button danger"
              disabled={busyId === confirmDeleteId}
              onClick={() => {
                const video = videos.find((v) => v.id === confirmDeleteId)
                setConfirmDeleteId(null)
                if (video) remove(video)
              }}
            >
              {busyId === confirmDeleteId ? 'Đang xóa…' : 'Xóa'}
            </button>
          </div>
        </Modal>
      )}

      {user.role === 'moderator' && (
        <section className="moderator-profile-stats" aria-label="Thống kê kiểm duyệt">
          <div className="moderator-profile-heading">
            <div>
              <span className="overline">KHÔNG GIAN MODERATOR</span>
              <h2>Hoạt động kiểm duyệt</h2>
            </div>
          </div>
          {moderationStatsError && <ErrorNote>{moderationStatsError}</ErrorNote>}
          <div className="moderator-stat-grid">
            <article>
              <span>Quyết định đã xử lý</span>
              <strong>{moderationStats?.decisions_count ?? '—'}</strong>
            </article>
            <article>
              <span>Video bị từ chối</span>
              <strong>{moderationStats?.rejected_videos_count ?? '—'}</strong>
            </article>
            <article>
              <span>Báo cáo đang chờ</span>
              <strong>{moderationStats?.open_reports_count ?? '—'}</strong>
            </article>
            <article>
              <span>Khiếu nại đã xử lý</span>
              <strong>{moderationStats?.handled_appeals_count ?? '—'}</strong>
            </article>
          </div>
        </section>
      )}

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
                        <strong>{video.caption || 'Không có mô tả'}</strong>
                        <span>
                          {formatDateTime(video.created_at)} · {formatBytes(video.size_bytes)}
                        </span>
                      </span>
                      <StatusBadge status={video.status} label={VIDEO_STATUS_LABEL[video.status] || video.status} />
                    </button>
                    <span className="video-row-actions">
                      <button
                        type="button"
                        className="button ghost small"
                        onClick={() => navigate(`/edit-video?video_id=${encodeURIComponent(video.id)}`)}
                      >
                        <Icon name="edit" size={14} /> Chỉnh sửa
                      </button>
                      <button
                        type="button"
                        className="icon-button danger"
                        onClick={() => setConfirmDeleteId(video.id)}
                        disabled={busyId === video.id}
                        aria-label="Xóa video"
                        title="Xóa video"
                      >
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
